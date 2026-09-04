from odoo import api, fields, models


class ItsmTicket(models.Model):
    """Rattache un ticket a un actif materiel - ajoute via _inherit depuis le
    module ITAM plutot que d'avoir pre-ajoute un champ mort dans itsm.ticket
    des la Phase 1, conformement a l'architecture d'extensibilite validee des
    le depart (les futures phases - CMDB, Problem/Change - etendront de la
    meme maniere)."""
    _inherit = 'itsm.ticket'

    equipment_id = fields.Many2one(
        'maintenance.equipment', string="Actif concerné",
        domain="[('employee_id', '=', employee_id)] if employee_id else []",
        help="Actif materiel concerne par ce ticket, le cas echeant.",
    )

    @api.onchange('employee_id')
    def _onchange_employee_id_itam(self):
        if self.equipment_id and self.employee_id and self.equipment_id.employee_id != self.employee_id:
            self.equipment_id = False
