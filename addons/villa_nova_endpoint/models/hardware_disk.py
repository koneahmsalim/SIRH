from odoo import fields, models

MEDIA_TYPE_SELECTION = [
    ('ssd', "SSD"),
    ('hdd', "HDD"),
    ('unknown', "Inconnu"),
]


class ItamHardwareDisk(models.Model):
    """Un poste a generalement plusieurs disques (contrairement au CPU/RAM/
    carte mere geres en champs simples sur l'actif) - remplace entierement a
    chaque enrolement/check-in par l'agent (voir
    maintenance_equipment._endpoint_apply_inventory), jamais d'accumulation
    de doublons."""
    _name = 'itam.hardware.disk'
    _description = "Disque physique (inventaire agent endpoint)"
    _order = 'equipment_id, name'

    equipment_id = fields.Many2one('maintenance.equipment', string="Actif", required=True,
                                    ondelete='cascade', index=True)
    name = fields.Char(string="Nom", required=True)
    model = fields.Char(string="Modèle")
    media_type = fields.Selection(MEDIA_TYPE_SELECTION, string="Type", default='unknown')
    size_gb = fields.Float(string="Capacité (Go)")
    serial_no = fields.Char(string="Numéro de série")
