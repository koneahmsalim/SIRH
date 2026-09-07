from odoo import fields, models


class ItsmApproval(models.Model):
    """Generalisation localisee annoncee des la Phase 3 : ajoute change_id
    au moteur d'approbation existant et surcharge _get_approval_target()
    plutot que de reconstruire le modele - le reste (action_approve/
    action_refuse, les etats) est reutilise tel quel."""
    _inherit = 'itsm.approval'

    change_id = fields.Many2one('itsm.change', string="Changement", ondelete='cascade', index=True)

    _sql_constraints = [
        ('target_required', 'CHECK (ticket_id IS NOT NULL OR change_id IS NOT NULL)',
         "Une approbation doit être liée à un ticket ou à un changement."),
    ]

    def _get_approval_target(self):
        self.ensure_one()
        return self.change_id or super()._get_approval_target()
