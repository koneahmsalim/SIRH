from datetime import timedelta

from odoo import _, api, fields, models


class HrAppraisalEvaluation(models.Model):
    _name = 'hr.appraisal.evaluation'
    _description = "Évaluation individuelle Villa Nova"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    cycle_id = fields.Many2one('hr.appraisal.cycle', required=True, ondelete='cascade')
    employee_id = fields.Many2one('hr.employee', string="Collaborateur évalué", required=True, tracking=True)
    manager_id = fields.Many2one('hr.employee', related='employee_id.parent_id', string="Manager", store=True)
    track = fields.Selection(
        [
            ('manager', "Auto-évaluation Manager"),
            ('collaborator', "Évaluation Collaborateur (par le Manager)"),
        ],
        required=True, tracking=True,
        help="Manager : le collaborateur encadre une équipe et s'auto-évalue sur ses "
             "compétences managériales. Collaborateur N-1 : son propre manager l'évalue.",
    )
    stage = fields.Selection(
        [
            ('self_eval_pending', "En attente d'auto-évaluation"),
            ('self_eval_done', "Auto-évaluation reçue"),
            ('direction_review_pending', "Analyse Direction en attente"),
            ('direction_done', "Note attribuée"),
            ('restitution_pending', "Entretien de restitution à programmer"),
            ('closed', "Clôturée"),
        ],
        default='self_eval_pending', tracking=True, group_expand='_expand_stages',
    )

    self_evaluation = fields.Text(
        string="Auto-évaluation / Évaluation",
        help="Objectifs trimestriels, compétences clés et résultats obtenus. Éléments "
             "justificatifs (rapports, feedbacks, réalisations) à joindre en pièce jointe.",
    )
    self_eval_deadline = fields.Datetime(string="Délai auto-évaluation (72h)")

    # Structure de l'evaluation : 60% Objectifs / 40% Competences
    score_objectifs = fields.Integer(
        string="Objectifs (/60)",
        help="Taux de réalisation, impact, respect des délais.",
    )
    score_techniques = fields.Integer(string="Techniques (/8)", help="Métier, outils, expertise.")
    score_comportementales = fields.Integer(string="Comportementales (/8)", help="Fiabilité, éthique, attitude.")
    score_relationnelles = fields.Integer(string="Relationnelles (/8)", help="Communication, collaboration.")
    score_manageriales = fields.Integer(string="Managériales (/8)", help="Leadership, gestion du temps, décision.")
    score_adaptabilite = fields.Integer(string="Adaptabilité & Apprentissage (/8)", help="Curiosité, résilience, agilité.")
    score_competences = fields.Integer(string="Compétences (/40)", compute='_compute_scores', store=True)
    score_total = fields.Integer(string="Note globale (/100)", compute='_compute_scores', store=True)

    direction_comments = fields.Text(string="Commentaires d'évaluation (Direction)")
    direction_deadline = fields.Datetime(string="Délai analyse Direction")

    restitution_deadline = fields.Datetime(string="Délai entretien de restitution")
    restitution_notes = fields.Text(string="Notes de l'entretien de restitution")
    pdi_text = fields.Text(
        string="Plan de Développement Individuel (PDI)",
        help="Formation, accompagnement, objectifs révisés, coaching ciblé, évolution de carrière, etc.",
    )

    @api.depends(
        'score_objectifs', 'score_techniques', 'score_comportementales',
        'score_relationnelles', 'score_manageriales', 'score_adaptabilite',
    )
    def _compute_scores(self):
        for evaluation in self:
            evaluation.score_competences = (
                evaluation.score_techniques + evaluation.score_comportementales
                + evaluation.score_relationnelles + evaluation.score_manageriales
                + evaluation.score_adaptabilite
            )
            evaluation.score_total = evaluation.score_objectifs + evaluation.score_competences

    def _expand_stages(self, stages, domain):
        return [key for key, _label in self._fields['stage'].selection]

    def _get_role_group_users(self, group_xmlid):
        group = self.env.ref(group_xmlid, raise_if_not_found=False)
        return group.users if group else self.env['res.users']

    def _get_direction_users(self):
        return self._get_role_group_users('villa_nova_recruitment.group_direction_generale')

    def _get_manager_rh_users(self):
        return self._get_role_group_users('villa_nova_appraisal.group_manager_rh')

    def _self_eval_responsible_user(self):
        """Manager : le collaborateur evalue s'auto-evalue lui-meme.
        Collaborateur N-1 : c'est son manager qui remplit le formulaire."""
        self.ensure_one()
        if self.track == 'manager':
            return self.employee_id.user_id
        return self.employee_id.parent_id.user_id

    # ------------------------------------------------------------------
    # Etape 1 : Auto-evaluation / evaluation par le manager (delai 72h)
    # ------------------------------------------------------------------
    def action_start(self):
        for evaluation in self:
            evaluation.self_eval_deadline = fields.Datetime.now() + timedelta(hours=72)
            responsible = evaluation._self_eval_responsible_user()
            if responsible:
                evaluation.activity_schedule(
                    'mail.mail_activity_data_todo',
                    summary=_("Compléter l'évaluation de %s (délai 72h)", evaluation.employee_id.name),
                    note=_(
                        "Cycle : %(cycle)s. Formulaire basé sur les objectifs fixés, les "
                        "compétences clés et les résultats obtenus. Vous pouvez joindre des "
                        "éléments justificatifs (rapports, feedbacks, réalisations).",
                        cycle=evaluation.cycle_id.name,
                    ),
                    date_deadline=fields.Date.context_today(evaluation) + timedelta(days=3),
                    user_id=responsible.id,
                )
                evaluation._send_notification(
                    responsible.partner_id,
                    _("Évaluation à compléter : %s", evaluation.cycle_id.name),
                    _(
                        "Merci de compléter le formulaire d'évaluation de %(employee)s sous 72h.",
                        employee=evaluation.employee_id.name,
                    ),
                )

    def action_submit_self_evaluation(self):
        for evaluation in self:
            if not evaluation.self_evaluation:
                continue
            evaluation.stage = 'self_eval_done'
            evaluation._start_direction_review()

    def _start_direction_review(self):
        self.ensure_one()
        delay = timedelta(hours=72) if self.track == 'manager' else timedelta(days=7)
        self.direction_deadline = fields.Datetime.now() + delay
        self.stage = 'direction_review_pending'
        users = self._get_direction_users()
        if self.track == 'collaborator':
            users |= self._get_manager_rh_users()
        for user in users:
            self.activity_schedule(
                'mail.mail_activity_data_todo',
                summary=_("Analyser l'évaluation de %s et attribuer une note", self.employee_id.name),
                note=_(
                    "Analyse critique de l'évaluation, appréciation des résultats au regard "
                    "des objectifs fixés, prise en compte des indicateurs de performance. "
                    "Attribuer une note globale (/100) et rédiger des commentaires."
                ),
                date_deadline=fields.Date.context_today(self) + (timedelta(days=3) if self.track == 'manager' else timedelta(days=7)),
                user_id=user.id,
            )

    # ------------------------------------------------------------------
    # Etape 2 : Analyse de la Direction et attribution de la note
    # ------------------------------------------------------------------
    def action_direction_validate(self):
        for evaluation in self:
            evaluation.stage = 'direction_done'
            evaluation._schedule_restitution()

    def _schedule_restitution(self):
        self.ensure_one()
        if self.track == 'manager':
            deadline = fields.Datetime.now() + timedelta(hours=72)
            responsible_users = self._get_direction_users()
        else:
            contract = self.employee_id.contract_id
            if contract and contract.date_end:
                deadline = fields.Datetime.to_datetime(contract.date_end) - timedelta(days=14)
            else:
                deadline = fields.Datetime.now() + timedelta(days=14)
            responsible_users = self._get_manager_rh_users()
            if self.employee_id.parent_id.user_id:
                responsible_users |= self.employee_id.parent_id.user_id
        self.restitution_deadline = deadline
        self.stage = 'restitution_pending'
        for user in responsible_users:
            self.activity_schedule(
                'mail.mail_activity_data_meeting',
                summary=_("Entretien de restitution : %s", self.employee_id.name),
                note=_(
                    "Présentation des résultats de l'évaluation, échange constructif sur les "
                    "points forts, axes d'amélioration et perspectives. Élaborer le plan de "
                    "développement individuel (PDI) si nécessaire."
                ),
                date_deadline=fields.Date.context_today(self),
                user_id=user.id,
            )
        self._send_notification(
            self.employee_id.user_id.partner_id,
            _("Votre évaluation a été analysée"),
            _("Un entretien de restitution va vous être proposé prochainement pour échanger sur les résultats."),
        )

    # ------------------------------------------------------------------
    # Etape 3 : Restitution et feedback
    # ------------------------------------------------------------------
    def action_close_restitution(self):
        for evaluation in self:
            evaluation.stage = 'closed'
            evaluation._send_notification(
                evaluation.employee_id.user_id.partner_id,
                _("Résultats de votre évaluation - %s", evaluation.cycle_id.name),
                _(
                    "Note globale : %(score)s/100 (Objectifs : %(obj)s/60, Compétences : %(comp)s/40). "
                    "Votre manager ou la RH reviendra vers vous pour tout complément.",
                    score=evaluation.score_total, obj=evaluation.score_objectifs,
                    comp=evaluation.score_competences,
                ),
            )

    def _send_notification(self, partner, subject, body):
        self.ensure_one()
        if not partner:
            return
        self.message_notify(partner_ids=partner.ids, subject=subject, body=body)
