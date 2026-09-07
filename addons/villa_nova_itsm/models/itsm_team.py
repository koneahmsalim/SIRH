from odoo import api, fields, models


class ItsmTeam(models.Model):
    """Equipe de support (N1, N2, Infrastructure...). Point d'entree pour
    l'assignation et le calcul de charge - toute logique de routage futur
    (round-robin, auto-assignation) se branchera ici plutot que sur
    l'agent directement, pour rester valable meme si l'equipe change de
    composition."""
    _name = 'itsm.team'
    _description = "Équipe de support ITSM"
    _inherit = ['mail.thread']
    _order = 'sequence, name'

    name = fields.Char(string="Nom", required=True, tracking=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)
    leader_id = fields.Many2one('res.users', string="Responsable d'équipe", tracking=True)
    member_ids = fields.Many2many('res.users', string="Agents")
    default_sla_policy_id = fields.Many2one('itsm.sla.policy', string="SLA par défaut")
    calendar_id = fields.Many2one(
        'resource.calendar', string="Horaires de l'équipe",
        default=lambda self: self.env.company.resource_calendar_id,
        help="Utilisé pour calculer les échéances SLA sur les heures réellement ouvrées de l'équipe.",
    )
    color = fields.Integer(string="Couleur")
    description = fields.Text(string="Description")

    escalation_level_ids = fields.One2many(
        'itsm.escalation.level', 'team_id', string="Niveaux d'escalade",
        help="Sans niveau configuré, l'escalade retombe sur le responsable d'équipe dès le "
             "dépassement du SLA (comportement historique).",
    )

    open_ticket_count = fields.Integer(compute='_compute_ticket_counts')
    member_count = fields.Integer(compute='_compute_member_count')

    @api.depends('member_ids')
    def _compute_member_count(self):
        for team in self:
            team.member_count = len(team.member_ids)

    def _compute_ticket_counts(self):
        Ticket = self.env['itsm.ticket']
        for team in self:
            team.open_ticket_count = Ticket.search_count([
                ('team_id', '=', team.id),
                ('state', 'not in', ['resolved', 'closed', 'cancelled']),
            ])

    def action_view_tickets(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.name,
            'res_model': 'itsm.ticket',
            'view_mode': 'list,kanban,form',
            'domain': [('team_id', '=', self.id)],
            'context': {'default_team_id': self.id},
        }
