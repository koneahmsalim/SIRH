from odoo import _, fields, models


class HrAppraisalCycle(models.Model):
    _name = 'hr.appraisal.cycle'
    _description = "Cycle d'évaluation Villa Nova"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'period_start desc'

    name = fields.Char(required=True, tracking=True)
    eval_type = fields.Selection(
        [
            ('performance', "Évaluation de la performance"),
            ('competences', "Évaluation des compétences"),
        ],
        string="Type d'évaluation", required=True, default='performance', tracking=True,
        help="Performance : mesure des résultats/objectifs atteints (mensuelle/trimestrielle). "
             "Compétences : savoirs, savoir-faire, savoir-être (annuelle/semestrielle).",
    )
    period_start = fields.Date(string="Début de la période", required=True)
    period_end = fields.Date(string="Fin de la période", required=True)
    objectifs_text = fields.Text(
        string="Objectifs du cycle (SMART / OKR)",
        help="Fixés par la Direction (Cheffe de Cabinet / PDG), déclinés par département, "
             "poste et niveau de responsabilité. SMART : Spécifiques, Mesurables, "
             "Atteignables, Réalistes, Temporels. OKR : Objectifs et Résultats Clés.",
    )
    employee_ids = fields.Many2many(
        'hr.employee', string="Collaborateurs concernés",
        help="Sélectionnez les collaborateurs inclus dans ce cycle. Au lancement, chacun "
             "reçoit une évaluation « Collaborateur » (par son manager) et, s'il encadre "
             "lui-même une équipe, une auto-évaluation « Manager » en plus.",
    )
    evaluation_ids = fields.One2many('hr.appraisal.evaluation', 'cycle_id', string="Évaluations")
    evaluation_count = fields.Integer(compute='_compute_evaluation_count')
    state = fields.Selection(
        [('draft', "Brouillon"), ('launched', "Lancé"), ('closed', "Clôturé")],
        default='draft', tracking=True,
    )

    def _compute_evaluation_count(self):
        for cycle in self:
            cycle.evaluation_count = len(cycle.evaluation_ids)

    def action_launch(self):
        """Phase 1 : Lancement du cycle. Genere les evaluations pour chaque
        collaborateur selectionne et demarre le circuit adequat (Manager
        et/ou Collaborateur N-1)."""
        Evaluation = self.env['hr.appraisal.evaluation']
        for cycle in self:
            for employee in cycle.employee_ids:
                is_manager = bool(self.env['hr.employee'].search_count([('parent_id', '=', employee.id)]))
                if is_manager:
                    evaluation = Evaluation.create({
                        'cycle_id': cycle.id,
                        'employee_id': employee.id,
                        'track': 'manager',
                    })
                    evaluation.action_start()
                if employee.parent_id:
                    evaluation = Evaluation.create({
                        'cycle_id': cycle.id,
                        'employee_id': employee.id,
                        'track': 'collaborator',
                    })
                    evaluation.action_start()
            cycle.state = 'launched'
            cycle.message_post(body=_("Cycle lancé : %s évaluation(s) créée(s).", len(cycle.evaluation_ids)))

    def action_close(self):
        self.write({'state': 'closed'})
