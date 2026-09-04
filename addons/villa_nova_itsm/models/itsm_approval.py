from odoo import api, fields, models, _
from odoo.exceptions import UserError

STATE_SELECTION = [
    ('pending', "En attente"),
    ('approved', "Approuvée"),
    ('refused', "Refusée"),
]


class ItsmApproval(models.Model):
    """Moteur d'approbation generique pour l'ITSM : demarre volontairement
    lie a un seul modele (itsm.ticket, via ticket_id) plutot que via un
    res_model/res_id generique - le seul consommateur reel aujourd'hui est
    le ticket (demande de service necessitant validation). Quand le Change
    Management (Phase 7) aura besoin du meme mecanisme, le generaliser a ce
    moment-la (ajouter change_id, ou basculer vers une reference
    generique) sera un refactor localise, pas une reconstruction."""
    _name = 'itsm.approval'
    _description = "Demande d'approbation ITSM"
    _inherit = ['mail.thread']
    _order = 'create_date desc'

    ticket_id = fields.Many2one('itsm.ticket', string="Ticket", required=True, ondelete='cascade', index=True)
    requested_by = fields.Many2one('res.users', string="Demandé par", default=lambda self: self.env.user, required=True)
    approver_id = fields.Many2one('res.users', string="Approbateur", required=True, tracking=True)
    state = fields.Selection(STATE_SELECTION, string="Statut", default='pending', required=True, tracking=True)
    request_date = fields.Datetime(string="Demandé le", default=fields.Datetime.now, required=True)
    decision_date = fields.Datetime(string="Décidé le")
    comment = fields.Text(string="Commentaire")

    def action_approve(self):
        for approval in self:
            if approval.state != 'pending':
                raise UserError(_("Cette demande a déjà été traitée."))
            approval.write({'state': 'approved', 'decision_date': fields.Datetime.now()})
            approval.ticket_id.message_post(body=_(
                "Approbation accordée par %(approver)s.", approver=approval.approver_id.name))

    def action_refuse(self):
        for approval in self:
            if approval.state != 'pending':
                raise UserError(_("Cette demande a déjà été traitée."))
            approval.write({'state': 'refused', 'decision_date': fields.Datetime.now()})
            approval.ticket_id.message_post(body=_(
                "Approbation refusée par %(approver)s.", approver=approval.approver_id.name))
