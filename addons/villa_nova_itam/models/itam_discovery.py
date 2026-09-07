import json

from odoo import _, api, fields, models

RESULT_SELECTION = [
    ('created', "Actif créé"),
    ('updated', "Actif mis à jour"),
    ('error', "Erreur"),
]


class ItamDiscoveryLog(models.Model):
    _name = 'itam.discovery.log'
    _description = "Journal de découverte ITAM"
    _order = 'create_date desc'

    equipment_id = fields.Many2one('maintenance.equipment', string="Actif")
    source_ip = fields.Char(string="IP source")
    hostname = fields.Char(string="Nom d'hôte signalé")
    result = fields.Selection(RESULT_SELECTION, string="Résultat", required=True)
    error_message = fields.Char(string="Message d'erreur")
    raw_payload = fields.Text(string="Payload brut")


class MaintenanceEquipmentDiscovery(models.Model):
    _inherit = 'maintenance.equipment'

    def _itam_discovery_upsert(self, vals, source_ip=None):
        """Point d'entree unique appele par le controleur de decouverte
        (agent externe authentifie par cle API). Retrouve l'actif par
        numero de serie puis par nom d'hote, le met a jour ou le cree, et
        journalise systematiquement le resultat (y compris les echecs) pour
        etre auditable - jamais de creation/mise a jour silencieuse."""
        Log = self.env['itam.discovery.log']
        serial_no = vals.get('serial_no')
        hostname = vals.get('hostname')
        try:
            equipment = self.browse()
            if serial_no:
                equipment = self.search([('serial_no', '=', serial_no)], limit=1)
            if not equipment and hostname:
                equipment = self.search([('hostname', '=', hostname)], limit=1)

            endpoint_vals = {
                'hostname': hostname,
                'ip_address': vals.get('ip_address'),
                'os_name': vals.get('os_name'),
                'os_version': vals.get('os_version'),
                'model': vals.get('model'),
                'serial_no': serial_no,
                'av_status': vals.get('av_status'),
                'patch_status': vals.get('patch_status'),
                'encryption_enabled': vals.get('encryption_enabled'),
                'last_seen': fields.Datetime.now(),
                'last_security_scan': fields.Datetime.now(),
            }
            endpoint_vals = {k: v for k, v in endpoint_vals.items() if v not in (None, '')}

            if equipment:
                equipment.write(endpoint_vals)
                result = 'updated'
            else:
                create_vals = dict(endpoint_vals)
                create_vals['name'] = hostname or serial_no or _("Actif découvert")
                create_vals['asset_status'] = 'in_stock'
                category = self.env.ref(
                    'villa_nova_itam.equipment_category_discovered', raise_if_not_found=False)
                if category:
                    create_vals['category_id'] = category.id
                equipment = self.create(create_vals)
                result = 'created'

            Log.create({
                'equipment_id': equipment.id,
                'source_ip': source_ip,
                'hostname': hostname,
                'result': result,
                'raw_payload': json.dumps(vals),
            })
            return equipment, result
        except Exception as e:
            Log.create({
                'source_ip': source_ip,
                'hostname': hostname,
                'result': 'error',
                'error_message': str(e),
                'raw_payload': json.dumps(vals),
            })
            raise
