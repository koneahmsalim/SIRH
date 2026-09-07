from odoo import api, fields, models


class MaintenanceEquipmentEndpoint(models.Model):
    """Etend encore maintenance.equipment (deja enrichi par les Phases 4-5
    ITAM/ESAM) plutot que de creer un modele d'actif parallele - decision
    d'architecture confirmee avec l'utilisateur pour cette Phase 2 Endpoint
    Management. N'ajoute que ce que la decouverte legere (Phase 5, API-key
    partagee) ne portait pas : detail materiel complet, disques/interfaces
    multiples, logiciels installes, utilisateur connecte - alimentes
    uniquement par un agent reel identifie individuellement (voir
    itsm.endpoint.agent + controllers/agent.py), jamais de saisie manuelle
    censee refleter un etat materiel constate."""
    _inherit = 'maintenance.equipment'

    endpoint_agent_ids = fields.One2many('itsm.endpoint.agent', 'equipment_id', string="Historique des agents")
    endpoint_agent_id = fields.Many2one(
        'itsm.endpoint.agent', string="Agent endpoint actif",
        compute='_compute_endpoint_agent_id', store=True,
    )
    endpoint_agent_state = fields.Selection(
        related='endpoint_agent_id.state', string="Statut de l'agent", readonly=True, store=True)

    @api.depends('endpoint_agent_ids.state')
    def _compute_endpoint_agent_id(self):
        for equipment in self:
            equipment.endpoint_agent_id = equipment.endpoint_agent_ids.filtered(
                lambda a: a.state == 'enrolled')[:1]

    cpu_model = fields.Char(string="Processeur")
    cpu_cores = fields.Integer(string="Cœurs physiques")
    cpu_logical_processors = fields.Integer(string="Processeurs logiques")
    ram_gb = fields.Float(string="RAM (Go)")
    motherboard = fields.Char(string="Carte mère")
    bios_version = fields.Char(string="Version du BIOS")
    gpu_model = fields.Char(string="Carte graphique")
    battery_present = fields.Boolean(string="Batterie présente")
    battery_health_percent = fields.Float(string="Santé de la batterie (%)")
    monitor_count = fields.Integer(string="Nombre d'écrans")
    logged_in_user = fields.Char(string="Utilisateur connecté")

    disk_ids = fields.One2many('itam.hardware.disk', 'equipment_id', string="Disques")
    disk_count = fields.Integer(string="Nombre de disques", compute='_compute_endpoint_counts')
    network_interface_ids = fields.One2many('itam.network.interface', 'equipment_id', string="Interfaces réseau")
    installed_software_ids = fields.One2many('itam.software.installed', 'equipment_id', string="Logiciels installés")
    installed_software_count = fields.Integer(string="Nombre de logiciels", compute='_compute_endpoint_counts')
    remote_command_ids = fields.One2many('itsm.remote.command', 'equipment_id', string="Commandes à distance")
    remote_command_count = fields.Integer(string="Nombre de commandes", compute='_compute_endpoint_counts')

    @api.depends('disk_ids', 'installed_software_ids', 'remote_command_ids')
    def _compute_endpoint_counts(self):
        for equipment in self:
            equipment.disk_count = len(equipment.disk_ids)
            equipment.installed_software_count = len(equipment.installed_software_ids)
            equipment.remote_command_count = len(equipment.remote_command_ids)

    def _endpoint_apply_inventory(self, vals):
        """Point d'application UNIQUE de l'inventaire agent, appele a la fois
        par l'enrolement et par chaque check-in (meme forme de payload) -
        evite toute divergence entre les deux chemins. 'vals' est le JSON
        decode envoye par l'agent Go, voir controllers/agent.py pour le
        schema exact et hooks.py/README pour un exemple complet."""
        self.ensure_one()
        hardware = vals.get('hardware') or {}
        security = vals.get('security') or {}
        network_interfaces = vals.get('network_interfaces') or []
        primary_iface = next((i for i in network_interfaces if i.get('is_primary')), None)
        if not primary_iface and network_interfaces:
            primary_iface = network_interfaces[0]

        equipment_vals = {
            'cpu_model': hardware.get('cpu_model'),
            'cpu_cores': hardware.get('cpu_cores'),
            'cpu_logical_processors': hardware.get('cpu_logical_processors'),
            'ram_gb': hardware.get('ram_gb'),
            'motherboard': hardware.get('motherboard'),
            'bios_version': hardware.get('bios_version'),
            'gpu_model': hardware.get('gpu_model'),
            'battery_present': hardware.get('battery_present'),
            'battery_health_percent': hardware.get('battery_health_percent'),
            'monitor_count': hardware.get('monitor_count'),
            'logged_in_user': vals.get('logged_in_user'),
            'last_seen': fields.Datetime.now(),
            'last_security_scan': fields.Datetime.now(),
        }
        if primary_iface and primary_iface.get('ip_address'):
            equipment_vals['ip_address'] = primary_iface['ip_address']
        if security.get('av_status'):
            equipment_vals['av_status'] = security['av_status']
        if security.get('patch_status'):
            equipment_vals['patch_status'] = security['patch_status']
        if 'encryption_enabled' in security:
            equipment_vals['encryption_enabled'] = security['encryption_enabled']
        equipment_vals = {k: v for k, v in equipment_vals.items() if v not in (None, '')}
        self.write(equipment_vals)

        self.disk_ids.unlink()
        for disk in vals.get('disks') or []:
            self.env['itam.hardware.disk'].create({
                'equipment_id': self.id,
                'name': disk.get('name') or disk.get('model') or 'Disque',
                'model': disk.get('model'),
                'media_type': disk.get('media_type') or 'unknown',
                'size_gb': disk.get('size_gb') or 0.0,
                'serial_no': disk.get('serial_no'),
            })

        self.network_interface_ids.unlink()
        for iface in network_interfaces:
            self.env['itam.network.interface'].create({
                'equipment_id': self.id,
                'name': iface.get('name') or 'Interface',
                'mac_address': iface.get('mac_address'),
                'ip_address': iface.get('ip_address'),
                'subnet_mask': iface.get('subnet_mask'),
                'gateway': iface.get('gateway'),
                'dns_servers': iface.get('dns_servers'),
                'dhcp_enabled': bool(iface.get('dhcp_enabled')),
                'is_primary': bool(iface.get('is_primary')),
            })

        self.installed_software_ids.unlink()
        software_vals = []
        for software in vals.get('software') or []:
            if not software.get('name'):
                continue
            software_vals.append({
                'equipment_id': self.id,
                'name': software['name'],
                'version': software.get('version'),
                'publisher': software.get('publisher'),
                'install_date': software.get('install_date') or False,
                'source': software.get('source') or 'registry',
            })
        if software_vals:
            self.env['itam.software.installed'].create(software_vals)

    def action_view_installed_software(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.name,
            'res_model': 'itam.software.installed',
            'view_mode': 'list,form',
            'domain': [('equipment_id', '=', self.id)],
        }

    def action_view_disks(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.name,
            'res_model': 'itam.hardware.disk',
            'view_mode': 'list,form',
            'domain': [('equipment_id', '=', self.id)],
        }

    def action_view_remote_commands(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.name,
            'res_model': 'itsm.remote.command',
            'view_mode': 'list,form',
            'domain': [('equipment_id', '=', self.id)],
            'context': {'default_equipment_id': self.id},
        }
