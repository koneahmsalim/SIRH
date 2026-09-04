from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ItsmTicketResolveWizard(models.TransientModel):
    _name = 'itsm.ticket.resolve.wizard'
    _description = "Assistant de résolution de ticket"

    ticket_ids = fields.Many2many('itsm.ticket', string="Tickets")
    close_notes = fields.Html(string="Notes de résolution", required=True)

    def action_confirm(self):
        self.ensure_one()
        self.ticket_ids.write({'state': 'resolved', 'close_notes': self.close_notes})
        for ticket in self.ticket_ids:
            ticket.message_post(body=_("Ticket résolu : %s") % self.close_notes)
        return {'type': 'ir.actions.act_window_close'}


class ItsmTicketPendingWizard(models.TransientModel):
    _name = 'itsm.ticket.pending.wizard'
    _description = "Assistant de mise en attente"

    ticket_ids = fields.Many2many('itsm.ticket', string="Tickets")
    pending_reason = fields.Char(string="Motif", required=True)

    def action_confirm(self):
        self.ensure_one()
        self.ticket_ids.write({'state': 'pending', 'pending_reason': self.pending_reason})
        for ticket in self.ticket_ids:
            ticket.message_post(body=_("Mis en attente : %s") % self.pending_reason)
        return {'type': 'ir.actions.act_window_close'}


class ItsmTicketCancelWizard(models.TransientModel):
    _name = 'itsm.ticket.cancel.wizard'
    _description = "Assistant d'annulation de ticket"

    ticket_ids = fields.Many2many('itsm.ticket', string="Tickets")
    cancel_reason = fields.Char(string="Motif", required=True)

    def action_confirm(self):
        self.ensure_one()
        self.ticket_ids.write({'state': 'cancelled', 'cancel_reason': self.cancel_reason})
        for ticket in self.ticket_ids:
            ticket.message_post(body=_("Ticket annulé : %s") % self.cancel_reason)
        return {'type': 'ir.actions.act_window_close'}


class ItsmTicketMergeWizard(models.TransientModel):
    """Fusion : le ticket source est marque merged_into_id + archive, ses
    messages sont recopies dans le ticket cible (conversation unifiee) et
    ses tickets enfants sont reattaches au ticket cible - evite de perdre
    le contexte deja echange avec le demandeur cote ticket source."""
    _name = 'itsm.ticket.merge.wizard'
    _description = "Assistant de fusion de tickets"

    source_ticket_id = fields.Many2one('itsm.ticket', required=True)
    target_ticket_id = fields.Many2one(
        'itsm.ticket', required=True, string="Fusionner dans",
        domain="[('id', '!=', source_ticket_id)]",
    )

    def action_confirm(self):
        self.ensure_one()
        if self.source_ticket_id == self.target_ticket_id:
            raise UserError(_("Impossible de fusionner un ticket avec lui-même."))
        target = self.target_ticket_id
        source = self.source_ticket_id

        target.message_post(body=_(
            "Fusionné avec le ticket %(source_ref)s (par %(user)s).",
            source_ref=source.name, user=self.env.user.name,
        ))
        for message in source.message_ids.filtered(lambda m: m.message_type != 'notification'):
            target.message_post(
                body=_("[Depuis %(ref)s] %(body)s", ref=source.name, body=message.body),
                author_id=message.author_id.id,
            )
        source.child_ticket_ids.write({'parent_ticket_id': target.id})
        source.write({'merged_into_id': target.id, 'state': 'cancelled', 'active': False})
        target.write({'linked_ticket_ids': [(4, source.id)]})
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'itsm.ticket',
            'res_id': target.id,
            'view_mode': 'form',
            'target': 'current',
        }
