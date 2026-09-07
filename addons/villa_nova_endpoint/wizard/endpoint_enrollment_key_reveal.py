from odoo import fields, models


class ItsmEndpointEnrollmentKeyReveal(models.TransientModel):
    """Transitoire par nature (TransientModel, purge automatique Odoo) : le
    jeton en clair ne doit exister que le temps de cette fenetre - jamais
    stocke sur itsm.endpoint.enrollment.key (seul key_hash y persiste)."""
    _name = 'itsm.endpoint.enrollment.key.reveal'
    _description = "Jeton d'enrôlement (affichage unique)"

    key_id = fields.Many2one('itsm.endpoint.enrollment.key', string="Clé", required=True, readonly=True)
    token = fields.Char(string="Jeton complet", readonly=True)
