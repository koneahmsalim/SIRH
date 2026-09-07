from odoo import fields, models


class ItsmTicket(models.Model):
    """Rattache un incident a un probleme - ajoute via _inherit depuis ce
    module plutot que pre-ajoute en Phase 1, meme architecture que
    equipment_id (villa_nova_itam)."""
    _inherit = 'itsm.ticket'

    problem_id = fields.Many2one(
        'itsm.problem', string="Problème lié",
        help="Problème (cause racine) dont cet incident est un symptôme.",
    )
