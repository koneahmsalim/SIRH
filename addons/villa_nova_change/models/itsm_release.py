from odoo import _, api, fields, models
from odoo.exceptions import UserError

STATE_SELECTION = [
    ('planned', "Planifiée"),
    ('in_progress', "En cours"),
    ('released', "Déployée"),
    ('cancelled', "Annulée"),
]

_ALLOWED_TRANSITIONS = {
    'planned': {'in_progress', 'cancelled'},
    'in_progress': {'released', 'cancelled'},
    'released': set(),
    'cancelled': set(),
}


class ItsmRelease(models.Model):
    _name = 'itsm.release'
    _description = "Release ITSM"
    _inherit = ['mail.thread']
    _order = 'target_date desc, create_date desc'

    name = fields.Char(string="Nom / Version", required=True, tracking=True)
    description = fields.Html(string="Description")
    state = fields.Selection(STATE_SELECTION, string="Statut", default='planned', required=True, tracking=True)
    target_date = fields.Date(string="Date cible", tracking=True)

    change_ids = fields.One2many('itsm.change', 'release_id', string="Changements inclus")
    change_count = fields.Integer(string="Nombre de changements", compute='_compute_change_count')
    unimplemented_change_count = fields.Integer(
        string="Changements non implémentés", compute='_compute_change_count',
        help="Changements de cette release qui ne sont pas encore au statut Implémenté.",
    )

    @api.depends('change_ids.state')
    def _compute_change_count(self):
        for release in self:
            release.change_count = len(release.change_ids)
            release.unimplemented_change_count = len(
                release.change_ids.filtered(lambda c: c.state != 'implemented'))

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
            for release in self:
                self._check_state_transition(release.state, vals['state'])
                if vals['state'] == 'released' and release.unimplemented_change_count:
                    raise UserError(_(
                        "%(count)d changement(s) de cette release ne sont pas encore implémentés - "
                        "impossible de marquer la release comme déployée.",
                        count=release.unimplemented_change_count))
        return super().write(vals)

    def action_start(self):
        self.write({'state': 'in_progress'})

    def action_release(self):
        self.write({'state': 'released'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_view_changes(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Changements inclus"),
            'res_model': 'itsm.change',
            'view_mode': 'list,form',
            'domain': [('release_id', '=', self.id)],
            'context': {'default_release_id': self.id},
        }
