from odoo import _, api, fields, models
from odoo.exceptions import UserError

STATE_SELECTION = [
    ('new', "Nouveau"),
    ('investigating', "En investigation"),
    ('known_error', "Erreur connue"),
    ('resolved', "Résolu"),
    ('closed', "Clôturé"),
]

PRIORITY_SELECTION = [
    ('low', "Basse"),
    ('medium', "Moyenne"),
    ('high', "Haute"),
    ('critical', "Critique"),
]

# Contrairement au ticket, un probleme ne "regresse" jamais vers "new" une
# fois l'investigation commencee - son cycle de vie est plus lineaire (pas
# de SLA de reponse, l'urgence est portee par les incidents lies).
_ALLOWED_TRANSITIONS = {
    'new': {'investigating', 'closed'},
    'investigating': {'known_error', 'resolved', 'closed'},
    'known_error': {'resolved', 'closed'},
    'resolved': {'closed', 'investigating'},
    'closed': {'investigating'},
}


class ItsmProblem(models.Model):
    _name = 'itsm.problem'
    _description = "Problème ITSM (analyse de cause racine)"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(string="Référence", default="Nouveau", copy=False, readonly=True)
    subject = fields.Char(string="Sujet", required=True, tracking=True)
    description = fields.Html(string="Description")
    state = fields.Selection(STATE_SELECTION, string="Statut", default='new', required=True, tracking=True)
    priority = fields.Selection(PRIORITY_SELECTION, string="Priorité", default='medium', tracking=True)

    team_id = fields.Many2one('itsm.team', string="Équipe")
    user_id = fields.Many2one('res.users', string="Responsable", tracking=True)

    root_cause = fields.Html(string="Cause racine")
    workaround = fields.Html(string="Solution de contournement")
    is_known_error = fields.Boolean(string="Erreur connue", compute='_compute_is_known_error', store=True)

    incident_ids = fields.One2many('itsm.ticket', 'problem_id', string="Incidents liés")
    incident_count = fields.Integer(string="Nombre d'incidents", compute='_compute_incident_count')
    change_ids = fields.One2many('itsm.change', 'problem_id', string="Changements liés")
    change_count = fields.Integer(string="Nombre de changements", compute='_compute_change_count')

    resolved_date = fields.Datetime(string="Résolu le", copy=False)
    closed_date = fields.Datetime(string="Clôturé le", copy=False)

    @api.depends('state')
    def _compute_is_known_error(self):
        for problem in self:
            problem.is_known_error = problem.state in ('known_error', 'resolved', 'closed')

    @api.depends('incident_ids')
    def _compute_incident_count(self):
        for problem in self:
            problem.incident_count = len(problem.incident_ids)

    @api.depends('change_ids')
    def _compute_change_count(self):
        for problem in self:
            problem.change_count = len(problem.change_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nouveau') == 'Nouveau':
                vals['name'] = self.env['ir.sequence'].next_by_code('itsm.problem') or 'Nouveau'
        return super().create(vals_list)

    def _check_state_transition(self, old_state, new_state):
        if old_state == new_state:
            return
        allowed = _ALLOWED_TRANSITIONS.get(old_state, set())
        if new_state not in allowed:
            raise UserError(_(
                "Transition non autorisée : %(old)s → %(new)s.",
                old=dict(STATE_SELECTION).get(old_state), new=dict(STATE_SELECTION).get(new_state)))

    def write(self, vals):
        if 'state' in vals:
            for problem in self:
                self._check_state_transition(problem.state, vals['state'])
        res = super().write(vals)
        if vals.get('state') == 'resolved':
            self.filtered(lambda p: not p.resolved_date).write({'resolved_date': fields.Datetime.now()})
        if vals.get('state') == 'closed':
            self.filtered(lambda p: not p.closed_date).write({'closed_date': fields.Datetime.now()})
        return res

    def action_start_investigation(self):
        self.write({'state': 'investigating'})

    def action_mark_known_error(self):
        self.write({'state': 'known_error'})

    def action_resolve(self):
        self.write({'state': 'resolved'})

    def action_close(self):
        self.write({'state': 'closed'})

    def action_view_incidents(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Incidents liés"),
            'res_model': 'itsm.ticket',
            'view_mode': 'list,form',
            'domain': [('problem_id', '=', self.id)],
            'context': {'default_problem_id': self.id, 'default_ticket_type': 'incident'},
        }

    def action_view_changes(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Changements liés"),
            'res_model': 'itsm.change',
            'view_mode': 'list,form',
            'domain': [('problem_id', '=', self.id)],
            'context': {'default_problem_id': self.id},
        }
