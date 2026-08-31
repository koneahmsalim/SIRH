from odoo import api, fields, models

STATUS_SELECTION = [
    ('on_track', "À jour"),
    ('at_risk', "À risque"),
    ('off_track', "En retard"),
    ('done', "Atteint"),
]

RISK_DAYS = 30
RISK_PROGRESS_THRESHOLD = 50


class ProjectGoal(models.Model):
    """Objectifs/OKR : fonctionnalite Asana totalement absente d'Odoo. Un
    objectif peut suivre sa progression automatiquement (moyenne
    d'avancement des projets rattaches, "travail associe" comme chez Asana)
    ou manuellement quand aucun projet n'est rattache (aspiration suivie a
    la main)."""
    _name = 'villa_nova_project.goal'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Objectif"
    _order = 'target_date, id'

    name = fields.Char(required=True)
    description = fields.Text()
    owner_id = fields.Many2one('res.users', string="Responsable", default=lambda self: self.env.user)
    target_date = fields.Date(string="Échéance")
    project_ids = fields.Many2many('project.project', string="Travail associé",
                                    help="Projets dont l'avancement fait progresser cet objectif automatiquement. "
                                         "Laisser vide pour suivre la progression manuellement.")
    progress = fields.Float(
        string="Avancement (%)", compute='_compute_progress', store=True, readonly=False,
        help="Calculé automatiquement à partir des projets associés si au moins un est renseigné, "
             "sinon modifiable librement.",
    )
    status = fields.Selection(STATUS_SELECTION, compute='_compute_status', store=True, string="Statut")
    active = fields.Boolean(default=True)

    @api.depends('project_ids')
    def _compute_progress(self):
        # project_ids.task_ids exclut les taches fermees (domaine natif
        # is_closed = False) : il faut chercher directement sur project.task
        # pour compter aussi les taches terminees dans le calcul.
        Task = self.env['project.task']
        for goal in self:
            if not goal.project_ids:
                continue  # laisse la valeur actuelle : mode manuel
            tasks = Task.search([('project_id', 'in', goal.project_ids.ids)])
            total = len(tasks) - len(tasks.filtered(lambda t: t.state == '1_canceled'))
            done = len(tasks.filtered(lambda t: t.state == '1_done'))
            goal.progress = round(done / total * 100) if total else 0

    @api.depends('progress', 'target_date')
    def _compute_status(self):
        today = fields.Date.context_today(self)
        for goal in self:
            if goal.progress >= 100:
                goal.status = 'done'
            elif goal.target_date and goal.target_date < today:
                goal.status = 'off_track'
            elif goal.target_date and (goal.target_date - today).days <= RISK_DAYS and goal.progress < RISK_PROGRESS_THRESHOLD:
                goal.status = 'at_risk'
            else:
                goal.status = 'on_track'
