from odoo import api, fields, models


class ItamDiscoveryDevice(models.Model):
    """Un appareil detecte par un scan ping sweep - rapproche best-effort
    d'un actif deja connu par adresse MAC (itam.network.interface, alimentee
    par les agents endpoint - Phase 2) ou par IP (maintenance.equipment.
    ip_address). Un scan reseau ne peut QUE constater qu'une IP repond au
    ping - il ne sait ni ce que c'est, ni s'il faut y deployer un agent :
    c'est a l'humain de decider en consultant device_type_guess, pas une
    creation automatique d'actif (contrairement a la decouverte par agent de
    la Phase 5 ITAM, qui elle est authentifiee et fiable)."""
    _name = 'itam.discovery.device'
    _description = "Appareil détecté par scan réseau"
    _order = 'ip_address'

    scan_id = fields.Many2one('itam.discovery.scan', string="Scan", required=True,
                               ondelete='cascade', index=True)
    ip_address = fields.Char(string="Adresse IP", required=True, index=True)
    mac_address = fields.Char(string="Adresse MAC", index=True)
    hostname = fields.Char(string="Nom d'hôte (résolu)")

    matched_equipment_id = fields.Many2one(
        'maintenance.equipment', string="Actif rapproché", compute='_compute_matched_equipment', store=True)
    device_type_guess = fields.Selection(
        [('known_agent', "Poste avec agent endpoint"), ('known_asset', "Actif ITAM connu (sans agent)"),
         ('unknown', "Inconnu - à qualifier")],
        string="Type (indicatif)", compute='_compute_matched_equipment', store=True,
    )

    @api.depends('mac_address', 'ip_address')
    def _compute_matched_equipment(self):
        Equipment = self.env['maintenance.equipment']
        Interface = self.env['itam.network.interface']
        for device in self:
            equipment = self.env['maintenance.equipment'].browse()
            if device.mac_address:
                iface = Interface.search([('mac_address', '=ilike', device.mac_address)], limit=1)
                equipment = iface.equipment_id
            if not equipment and device.ip_address:
                equipment = Equipment.search([('ip_address', '=', device.ip_address)], limit=1)

            device.matched_equipment_id = equipment.id if equipment else False
            if equipment and equipment.endpoint_agent_id:
                device.device_type_guess = 'known_agent'
            elif equipment:
                device.device_type_guess = 'known_asset'
            else:
                device.device_type_guess = 'unknown'

    def action_create_asset(self):
        """Cree un actif ITAM minimal a partir d'un appareil non rapproche -
        point de depart pour ensuite deployer un agent dessus, jamais un
        actif "complet" invente : seuls les champs reellement observes par
        le scan sont renseignes."""
        equipments = self.env['maintenance.equipment']
        for device in self:
            if device.matched_equipment_id:
                continue
            equipment = self.env['maintenance.equipment'].create({
                'name': device.hostname or device.ip_address,
                'hostname': device.hostname,
                'ip_address': device.ip_address,
                'asset_status': 'in_stock',
            })
            device.matched_equipment_id = equipment.id
            equipments |= equipment
        return {
            'type': 'ir.actions.act_window',
            'name': "Actifs créés",
            'res_model': 'maintenance.equipment',
            'view_mode': 'list,form',
            'domain': [('id', 'in', equipments.ids)],
        }
