from odoo import fields, models


class ItsmApproval(models.Model):
    """Meme generalisation localisee que villa_nova_change/itsm_approval_change.py
    et villa_nova_endpoint/approval_remote_command.py : ajoute purchase_request_id
    et surcharge _get_approval_target()/action_approve/action_refuse. Pas de
    CHECK SQL partage (voir le commentaire detaille dans les deux autres
    fichiers - un tel CHECK ne peut pas etre maintenu correctement a travers
    des modules independants qui ne se connaissent pas entre eux)."""
    _inherit = 'itsm.approval'

    purchase_request_id = fields.Many2one('itam.purchase.request', string="Demande d'achat",
                                           ondelete='cascade', index=True)

    def _get_approval_target(self):
        self.ensure_one()
        return self.purchase_request_id or super()._get_approval_target()

    def action_approve(self):
        super().action_approve()
        for approval in self:
            if approval.purchase_request_id and approval.state == 'approved':
                approval.purchase_request_id.write({'state': 'approved'})

    def action_refuse(self):
        super().action_refuse()
        for approval in self:
            if approval.purchase_request_id and approval.state == 'refused':
                approval.purchase_request_id.write({'state': 'refused'})
