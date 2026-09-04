from odoo import fields, models


class ItsmTicketTime(models.Model):
    """Journal de temps passe, volontairement independant de la pile
    comptable/analytique (account.analytic.line) : ce module ne doit pas
    dependre de 'analytic'/'sale' juste pour un champ de duree. Une
    integration vers la comptabilite analytique, si besoin un jour,
    s'ajoutera proprement via un module de liaison plutot qu'en imposant
    cette dependance a tout le Service Desk."""
    _name = 'itsm.ticket.time'
    _description = "Temps passé sur un ticket"
    _order = 'date desc, id desc'

    ticket_id = fields.Many2one('itsm.ticket', string="Ticket", required=True, ondelete='cascade', index=True)
    user_id = fields.Many2one('res.users', string="Agent", default=lambda self: self.env.user, required=True)
    date = fields.Date(string="Date", default=fields.Date.context_today, required=True)
    duration = fields.Float(string="Durée (h)", required=True)
    description = fields.Char(string="Description")
