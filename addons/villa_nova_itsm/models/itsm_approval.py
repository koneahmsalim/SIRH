from odoo import api, fields, models, _
from odoo.exceptions import UserError

STATE_SELECTION = [
    ('pending', "En attente"),
    ('approved', "Approuvée"),
    ('refused', "Refusée"),
]


class ItsmApproval(models.Model):
    """Moteur d'approbation generique pour l'ITSM. Le Change Management
    (villa_nova_change, Phase 7) etend ce modele via _inherit pour ajouter
    change_id et surcharge _get_approval_target() - refactor localise plutot
    que reconstruction, comme annonce des la Phase 3 : ticket_id n'est plus
    required ici pour permettre une approbation liee a un changement sans
    ticket, mais le comportement existant (approbations de ticket) est
    inchange."""
    _name = 'itsm.approval'
    _description = "Demande d'approbation ITSM"
    _inherit = ['mail.thread']
    _order = 'create_date desc'

    ticket_id = fields.Many2one('itsm.ticket', string="Ticket", ondelete='cascade', index=True)
    requested_by = fields.Many2one('res.users', string="Demandé par", default=lambda self: self.env.user, required=True)
    approver_id = fields.Many2one('res.users', string="Approbateur", required=True, tracking=True)
    state = fields.Selection(STATE_SELECTION, string="Statut", default='pending', required=True, tracking=True)
    request_date = fields.Datetime(string="Demandé le", default=fields.Datetime.now, required=True)
    decision_date = fields.Datetime(string="Décidé le")
    comment = fields.Text(string="Commentaire")

    def _get_approval_target(self):
        """Retourne l'enregistrement concerne par cette approbation. Point
        d'extension unique : le Change Management (villa_nova_change)
        surcharge cette methode pour ajouter change_id sans toucher au
        reste du moteur - le refactor localise annonce des la Phase 3."""
        self.ensure_one()
        return self.ticket_id

    def action_approve(self):
        for approval in self:
            if approval.state != 'pending':
                raise UserError(_("Cette demande a déjà été traitée."))
            approval.write({'state': 'approved', 'decision_date': fields.Datetime.now()})
            target = approval._get_approval_target()
            if target:
                target.message_post(body=_(
                    "Approbation accordée par %(approver)s.", approver=approval.approver_id.name))

    def action_refuse(self):
        for approval in self:
            if approval.state != 'pending':
                raise UserError(_("Cette demande a déjà été traitée."))
            approval.write({'state': 'refused', 'decision_date': fields.Datetime.now()})
            target = approval._get_approval_target()
            if target:
                target.message_post(body=_(
                    "Approbation refusée par %(approver)s.", approver=approval.approver_id.name))
