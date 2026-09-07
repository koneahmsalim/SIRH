from odoo import fields, models


class ItsmApproval(models.Model):
    """Meme generalisation localisee que villa_nova_change/itsm_approval_change.py :
    ajoute remote_command_id au moteur d'approbation existant et surcharge
    _get_approval_target(), sans toucher au reste (action_approve/
    action_refuse generiques reutilises tels quels). La contrainte SQL
    target_required est redefinie ici pour inclure ce troisieme type de
    cible - Odoo fusionne les _sql_constraints par nom a travers les
    modules, la derniere definition chargee (celle-ci, villa_nova_endpoint
    dependant de villa_nova_change) remplace la precedente en base."""
    _inherit = 'itsm.approval'

    remote_command_id = fields.Many2one('itsm.remote.command', string="Commande à distance",
                                         ondelete='cascade', index=True)

    _sql_constraints = [
        ('target_required',
         'CHECK (ticket_id IS NOT NULL OR change_id IS NOT NULL OR remote_command_id IS NOT NULL)',
         "Une approbation doit être liée à un ticket, un changement ou une commande à distance."),
    ]

    def _get_approval_target(self):
        self.ensure_one()
        return self.remote_command_id or super()._get_approval_target()

    def action_approve(self):
        super().action_approve()
        for approval in self:
            if approval.remote_command_id and approval.state == 'approved':
                approval.remote_command_id.write({'state': 'pending'})

    def action_refuse(self):
        super().action_refuse()
        for approval in self:
            if approval.remote_command_id and approval.state == 'refused':
                approval.remote_command_id.write({'state': 'refused'})
