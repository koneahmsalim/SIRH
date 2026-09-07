from odoo import _, api, fields, models
from odoo.exceptions import UserError

CHANGE_TYPE_SELECTION = [
    ('standard', "Standard (pré-approuvé, faible risque)"),
    ('normal', "Normal (nécessite l'approbation du CAB)"),
    ('emergency', "Urgence"),
]

STATE_SELECTION = [
    ('draft', "Brouillon"),
    ('submitted', "Soumis"),
    ('scheduled', "Planifié"),
    ('in_progress', "En cours"),
    ('implemented', "Implémenté"),
    ('failed', "Échoué"),
    ('cancelled', "Annulé"),
]

RISK_LEVEL_SELECTION = [
    ('low', "Faible"),
    ('medium', "Moyen"),
    ('high', "Élevé"),
]

APPROVAL_STATE_SELECTION = [
    ('none', "Aucune"),
    ('to_request', "À demander"),
    ('pending', "En attente"),
    ('approved', "Approuvée"),
    ('refused', "Refusée"),
]

_ALLOWED_TRANSITIONS = {
    'draft': {'submitted', 'cancelled'},
    'submitted': {'scheduled', 'draft', 'cancelled'},
    'scheduled': {'in_progress', 'cancelled'},
    'in_progress': {'implemented', 'failed'},
    'implemented': set(),
    'failed': {'scheduled', 'cancelled'},
    'cancelled': set(),
}

# Un changement standard est considere pre-approuve (procedure deja
# validee a l'avance par le CAB, ex. redemarrage planifie) - pas besoin
# d'approbation individuelle a chaque fois, contrairement a normal/emergency.
CHANGE_TYPES_REQUIRING_APPROVAL = ('normal', 'emergency')


class ItsmChange(models.Model):
    _name = 'itsm.change'
    _description = "Changement ITSM"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(string="Référence", default="Nouveau", copy=False, readonly=True)
    subject = fields.Char(string="Sujet", required=True, tracking=True)
    description = fields.Html(string="Description")
    change_type = fields.Selection(CHANGE_TYPE_SELECTION, string="Type", default='normal', required=True, tracking=True)
    state = fields.Selection(STATE_SELECTION, string="Statut", default='draft', required=True, tracking=True)
    risk_level = fields.Selection(RISK_LEVEL_SELECTION, string="Niveau de risque", default='medium', tracking=True)

    team_id = fields.Many2one('itsm.team', string="Équipe")
    requested_by = fields.Many2one('res.users', string="Demandé par", default=lambda self: self.env.user)
    user_id = fields.Many2one('res.users', string="Implémenté par", tracking=True)

    implementation_plan = fields.Html(string="Plan d'implémentation")
    backout_plan = fields.Html(string="Plan de retour arrière")

    scheduled_start = fields.Datetime(string="Début planifié")
    scheduled_end = fields.Datetime(string="Fin planifiée")
    actual_start = fields.Datetime(string="Début réel", copy=False)
    actual_end = fields.Datetime(string="Fin réelle", copy=False)

    problem_id = fields.Many2one('itsm.problem', string="Problème lié")
    release_id = fields.Many2one('itsm.release', string="Release")
    equipment_ids = fields.Many2many(
        'maintenance.equipment', string="Actifs / CI concernés",
        help="Éléments de configuration touchés par ce changement - sert de base à l'aperçu d'impact CMDB.",
    )

    approval_ids = fields.One2many('itsm.approval', 'change_id', string="Approbations")
    approval_state = fields.Selection(
        APPROVAL_STATE_SELECTION, string="Statut d'approbation",
        compute='_compute_approval_state', store=True,
    )
    requires_approval = fields.Boolean(
        string="Nécessite une approbation", compute='_compute_requires_approval', store=True,
    )

    @api.depends('change_type')
    def _compute_requires_approval(self):
        for change in self:
            change.requires_approval = change.change_type in CHANGE_TYPES_REQUIRING_APPROVAL

    @api.depends('approval_ids.state', 'requires_approval')
    def _compute_approval_state(self):
        for change in self:
            if not change.requires_approval:
                change.approval_state = 'none'
                continue
            approvals = change.approval_ids
            if not approvals:
                change.approval_state = 'to_request'
            elif any(a.state == 'refused' for a in approvals):
                change.approval_state = 'refused'
            elif all(a.state == 'approved' for a in approvals):
                change.approval_state = 'approved'
            else:
                change.approval_state = 'pending'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nouveau') == 'Nouveau':
                vals['name'] = self.env['ir.sequence'].next_by_code('itsm.change') or 'Nouveau'
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
            for change in self:
                self._check_state_transition(change.state, vals['state'])
        res = super().write(vals)
        if vals.get('state') == 'in_progress':
            self.filtered(lambda c: not c.actual_start).write({'actual_start': fields.Datetime.now()})
        if vals.get('state') in ('implemented', 'failed'):
            self.filtered(lambda c: not c.actual_end).write({'actual_end': fields.Datetime.now()})
        return res

    def action_submit(self):
        self.write({'state': 'submitted'})

    def action_request_cab_approval(self):
        self.ensure_one()
        if not self.requires_approval:
            raise UserError(_("Ce type de changement ne nécessite pas d'approbation CAB."))
        approver = self.team_id.leader_id
        if not approver:
            raise UserError(_("Aucun responsable d'équipe à qui demander l'approbation - définissez une équipe."))
        self.env['itsm.approval'].create({
            'change_id': self.id,
            'approver_id': approver.id,
        })
        self.message_post(body=_("Approbation CAB demandée à %(approver)s.", approver=approver.name))

    def action_schedule(self):
        self.ensure_one()
        if self.requires_approval and self.approval_state != 'approved':
            raise UserError(_("Ce changement doit être approuvé par le CAB avant d'être planifié."))
        self.write({'state': 'scheduled'})

    def action_start_implementation(self):
        self.write({'state': 'in_progress'})

    def action_implement(self):
        self.write({'state': 'implemented'})

    def action_fail(self):
        self.write({'state': 'failed'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_cmdb_impact_preview(self):
        """Reutilise le moteur d'analyse d'impact du CMDB (Phase 6) pour
        montrer, avant approbation/planification, ce qui serait affecte si
        les CI vises par ce changement etaient indisponibles pendant les
        travaux - integration inter-phases plutot que reimplementer une
        logique d'impact separee."""
        self.ensure_one()
        if not self.equipment_ids:
            raise UserError(_("Renseignez d'abord les actifs/CI concernés par ce changement."))
        Relation = self.env['cmdb.relation']
        all_equipment = self.env['maintenance.equipment'].browse()
        all_services = self.env['itsm.service'].browse()
        for equipment in self.equipment_ids:
            equip, services = Relation._impact_analysis(equipment._cmdb_ref())
            all_equipment |= equip
            all_services |= services
        all_equipment -= self.equipment_ids

        if not all_equipment and not all_services:
            html = _("<p>Aucun autre élément de configuration ne dépend des CI visés par ce "
                      "changement (<b>%(names)s</b>).</p>", names=', '.join(self.equipment_ids.mapped('display_name')))
        else:
            rows = ["<li><b>%s</b> (%s)</li>" % (e.display_name, _("Actif matériel")) for e in all_equipment]
            rows += ["<li><b>%s</b> (%s)</li>" % (s.display_name, _("Service")) for s in all_services]
            html = _(
                "<p>Pendant ce changement sur <b>%(names)s</b>, %(count)d autre(s) élément(s) de "
                "configuration pourraient être impactés :</p><ul>%(rows)s</ul>",
                names=', '.join(self.equipment_ids.mapped('display_name')),
                count=len(all_equipment) + len(all_services), rows=''.join(rows),
            )
        wizard = self.env['cmdb.impact.analysis.wizard'].create({
            'ci_name': self.subject,
            'result_html': html,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _("Aperçu d'impact"),
            'res_model': 'cmdb.impact.analysis.wizard',
            'view_mode': 'form',
            'res_id': wizard.id,
            'target': 'new',
        }
