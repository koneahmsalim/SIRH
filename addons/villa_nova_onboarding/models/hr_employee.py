from datetime import timedelta

from odoo import _, api, fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    x_onboarding_started = fields.Boolean(string="Onboarding démarré", copy=False)
    x_onboarding_survey_sent = fields.Boolean(string="Enquête J+30 envoyée", copy=False)
    x_onboarding_survey_j90_sent = fields.Boolean(string="Enquête J+90 envoyée", copy=False)
    x_trial_validation_status = fields.Selection(
        related='contract_id.x_trial_validation_status', store=True,
        string="Validation période d'essai",
    )

    def _get_onboarding_recipient_email(self):
        self.ensure_one()
        return self.private_email or self.work_email

    def _get_role_group_users(self, group_xmlid):
        group = self.env.ref(group_xmlid, raise_if_not_found=False)
        return group.users if group else self.env['res.users']

    # ------------------------------------------------------------------
    # Annexe 1 : Checklist Pre-Onboarding
    # ------------------------------------------------------------------
    def action_villa_nova_start_onboarding(self):
        """Declenchee des que l'employe est cree (Etape 6 du recrutement,
        "Contrat signe"). Cree les 6 taches de la checklist pre-onboarding,
        chacune assignee au bon role, et envoie les emails de preparation
        aux services internes ainsi que le premier email au candidat."""
        for employee in self:
            if employee.x_onboarding_started:
                continue
            employee.x_onboarding_started = True

            checklist = [
                (
                    "Création des accès informatiques",
                    "villa_nova_onboarding.group_support_it",
                    "Création de l'adresse email professionnelle, accès aux outils internes "
                    "(Teams, SharePoint, Asana, etc.), configuration des mots de passe, "
                    "accès personnalisé au portail d'onboarding.",
                ),
                (
                    "Préparation du poste de travail",
                    "villa_nova_onboarding.group_office_manager",
                    "Bureau attribué et propre, fournitures de bureau disponibles.",
                ),
                (
                    "Attribution du matériel",
                    "villa_nova_onboarding.group_support_it",
                    "Ordinateur portable / PC, téléphone professionnel (si applicable), "
                    "accessoires (souris, casque, etc.).",
                ),
                (
                    "Désignation du parrain / de la marraine",
                    None,
                    "Choisir le parrain selon les critères (volontaire, ancienneté ≥ 6 mois, "
                    "posture exemplaire), puis le renseigner dans le champ « Coach / Parrain » "
                    "de la fiche employé : le briefing du parrain partira automatiquement.",
                ),
                (
                    "Communication interne de bienvenue",
                    "villa_nova_onboarding.group_communication",
                    "Annonce dans le groupe WhatsApp (à faire manuellement), email d'annonce à "
                    "toute l'équipe (envoyé automatiquement), mise à jour de l'organigramme.",
                ),
                (
                    "Préparation des documents à signer",
                    None,
                    "Contrat de travail, accord de confidentialité, règlement intérieur, "
                    "attestation de lecture.",
                ),
                (
                    "Création du dossier administratif",
                    None,
                    "Attribution du matricule selon l'ordre d'arrivée, fiche d'identification, "
                    "RIB, CNI, casier judiciaire, etc.",
                ),
                (
                    "Programmation de la visite médicale d'embauche",
                    None,
                    "Organiser le rendez-vous médical d'embauche avant ou peu après le jour J.",
                ),
            ]
            for summary, group_xmlid, note in checklist:
                users = self._get_role_group_users(group_xmlid) if group_xmlid else employee.job_id.user_id
                for user in users:
                    employee.activity_schedule(
                        'mail.mail_activity_data_todo',
                        summary=summary,
                        note=note,
                        user_id=user.id,
                    )

            employee._schedule_manager_onboarding_tasks()
            employee._schedule_integration_timeline()

            employee._send_onboarding_template('villa_nova_onboarding.mail_template_portail_onboarding')
            employee._send_onboarding_template(
                'villa_nova_onboarding.mail_template_prep_it', group_xmlid='villa_nova_onboarding.group_support_it',
            )
            employee._send_onboarding_template(
                'villa_nova_onboarding.mail_template_prep_office',
                group_xmlid='villa_nova_onboarding.group_office_manager',
            )
            employee._send_onboarding_template(
                'villa_nova_onboarding.mail_template_prep_communication',
                group_xmlid='villa_nova_onboarding.group_communication',
            )
            employee._send_onboarding_template(
                'villa_nova_onboarding.mail_template_comptabilite',
                group_xmlid='villa_nova_onboarding.group_comptabilite',
            )
            employee._send_onboarding_template(
                'villa_nova_onboarding.mail_template_annonce_interne',
                partners=self.env['hr.employee'].search([('active', '=', True)]).mapped('user_id.partner_id'),
            )

    def _schedule_manager_onboarding_tasks(self):
        """Role "Manager" (Procedure d'integration, II - Acteurs & roles cles) :
        integration metier, evaluation des resultats, motivation continue.
        Couvre tous les jalons du parcours J-a-J180 qui reviennent au manager.
        Declenchee a la fois au demarrage de l'onboarding et, si le manager est
        designe plus tard, au moment ou le champ "Manager" est renseigne (voir
        write()) : jamais de jalon manager perdu, quel que soit l'ordre des
        etapes. Le bilan de periode d'essai est gere separement (voir
        hr.contract), des qu'un contrat avec date de fin d'essai existe."""
        self.ensure_one()
        if not self.parent_id or not self.parent_id.user_id:
            # Pas de manager assigne pour l'instant : a faire manuellement via la
            # fiche employe (champ "Manager"). Les jalons partiront automatiquement
            # des que ce champ sera renseigne.
            return
        start = self.joining_date or fields.Date.context_today(self)
        manager_timeline = [
            (0, "12h00-14h00 : Déjeuner d'équipe", "Déjeuner convivial avec l'équipe directe et/ou le manager."),
            (0, "14h00-15h00 : Rencontre avec le manager", "Objectifs à court/moyen terme, clarification des rôles et responsabilités, attentes."),
            (30, "Point d'intégration métier (J+30)", "Faire un point sur la prise de poste, évaluer les premiers résultats et maintenir la motivation du collaborateur."),
            (60, "Revue des objectifs avec le manager (J+60)", "Point d'avancement sur les objectifs fixés à l'arrivée."),
            (75, "Feedback croisé Manager / RH / collaborateur", "Partage croisé des retours à mi-parcours du trimestre 1."),
            (90, "Évaluation finale d'intégration (J+90)", "Évaluer la montée en compétence et la posture du collaborateur."),
            (120, "Intégration dans un projet transversal (si applicable)", "À évaluer selon les besoins de l'organisation."),
            (180, "Entretien de performance anticipé (6 mois)", "Entretien de performance formel à 6 mois."),
            (180, "Mise en place du Plan de Développement Individuel (PDI)", "Définir le PDI du collaborateur avec son manager."),
        ]
        for days, summary, note in manager_timeline:
            self.activity_schedule(
                'mail.mail_activity_data_todo',
                summary=summary,
                note=note,
                date_deadline=start + timedelta(days=days),
                user_id=self.parent_id.user_id.id,
            )

    def _schedule_integration_timeline(self):
        """Parcours J-7 a J180 (Procedure d'integration Villa Nova, sections
        3.2 a 3.6) pour les acteurs disponibles des le demarrage de l'onboarding
        (RH, Direction Generale, IT, Communication). Les jalons Manager et
        Parrain sont geres a part (voir _schedule_manager_onboarding_tasks et
        _action_villa_nova_coach_assigned) car leurs destinataires ne sont
        souvent designes qu'apres coup."""
        self.ensure_one()
        start = self.joining_date or fields.Date.context_today(self)
        rh_users = self.job_id.user_id
        dg_users = self._get_role_group_users('villa_nova_recruitment.group_direction_generale')
        it_users = self._get_role_group_users('villa_nova_onboarding.group_support_it')
        com_users = self._get_role_group_users('villa_nova_onboarding.group_communication')

        # (jours depuis joining_date, resume, note, destinataires)
        timeline = [
            # Phase 2 : Jour J - Accueil & Immersion (agenda indicatif ; Odoo ne
            # gere pas d'horaire sur les taches, l'heure est indiquee dans le titre)
            (0, "08h00-09h30 : Accueil personnalisé", "Réception, mot de bienvenue, présentation équipe RH, remise du welcome pack.", rh_users),
            (0, "09h30-10h15 : Présentation de l'entreprise", "Histoire du groupe, mission, valeurs, vision, culture, introduction aux filiales.", dg_users | rh_users),
            (0, "10h15-10h45 : Visite des locaux", "Tour guidé de La Villa Nova, présentation des espaces et des équipes.", rh_users),
            (0, "10h45-11h15 : Rencontre avec le Support IT", "Attribution du matériel informatique, badge, présentation des outils numériques.", it_users),
            (0, "11h15-12h00 : Formalités administratives", "Signature des contrats, règlement intérieur, charte, remise des documents RH.", rh_users),
            (0, "15h00-15h30 : Présentation des politiques internes", "Horaires, congés, sécurité, communication, accès intranet / livret d'accueil.", rh_users),
            (0, "16h30-17h00 : Bilan de la journée", "Recueillir les premières impressions du collaborateur, répondre aux questions.", rh_users),

            # Phase 3 : Semaine d'immersion (J1 a J5)
            (1, "Formation aux outils internes", "Asana, Intranet, messagerie.", it_users),
            (2, "Modules e-learning à assigner", "Procédures RH, finance, sécurité, organisation interne.", rh_users),
            (3, "QCM de compréhension (J+3)", "Administrer le QCM d'évaluation de la compréhension (contenu à préparer par la RH).", rh_users),
            (4, "Atelier « Nos valeurs & notre culture »", "Animation par la commission sociale.", com_users),
            (5, "Feedback 1 : RH & collaborateur (J+5)", "Premier échange formel sur les impressions à chaud.", rh_users),

            # Phase 4 : Suivi du 1er mois (J6 a J30) - le coaching hebdo est gere
            # des la designation du parrain, voir _action_villa_nova_coach_assigned
            (25, "Évaluation intermédiaire des acquis", "QCM et mise en pratique (contenu à préparer par la RH).", rh_users),
            (30, "Entretien RH (J+30)", "Points forts, points d'attention, suggestions.", rh_users),
        ]
        for days, summary, note, users in timeline:
            for user in users:
                self.activity_schedule(
                    'mail.mail_activity_data_todo',
                    summary=summary,
                    note=note,
                    date_deadline=start + timedelta(days=days),
                    user_id=user.id,
                )

    def _send_onboarding_template(self, template_xmlid, group_xmlid=None, partners=None):
        self.ensure_one()
        template = self.env.ref(template_xmlid, raise_if_not_found=False)
        if not template:
            return
        if group_xmlid:
            partners = self._get_role_group_users(group_xmlid).mapped('partner_id')
        if partners is not None:
            if not partners:
                return
            template.send_mail(
                self.id, force_send=True, email_values={'recipient_ids': [(6, 0, partners.ids)]},
            )
        else:
            if not self._get_onboarding_recipient_email():
                return
            template.send_mail(self.id, force_send=True)

    # ------------------------------------------------------------------
    # Annexe 2 (bienvenue perso + parrain) / Annexe 3 (suivi hebdomadaire)
    # ------------------------------------------------------------------
    def write(self, vals):
        newly_coached = self.env['hr.employee']
        newly_managed = self.env['hr.employee']
        if 'coach_id' in vals and vals.get('coach_id'):
            newly_coached = self.filtered(lambda e: not e.coach_id)
        if 'parent_id' in vals and vals.get('parent_id'):
            newly_managed = self.filtered(lambda e: not e.parent_id)
        res = super().write(vals)
        for employee in newly_coached:
            employee._action_villa_nova_coach_assigned()
        for employee in newly_managed:
            if employee.x_onboarding_started:
                employee._schedule_manager_onboarding_tasks()
        return res

    def _action_villa_nova_coach_assigned(self):
        self.ensure_one()
        self._send_onboarding_template('villa_nova_onboarding.mail_template_bienvenue_personnalise')
        if self.coach_id.user_id:
            self._send_onboarding_template(
                'villa_nova_onboarding.mail_template_briefing_parrain',
                partners=self.coach_id.user_id.partner_id,
            )
            start = self.joining_date or fields.Date.context_today(self)
            self.activity_schedule(
                'mail.mail_activity_data_todo',
                summary="15h00-15h30 : Rencontre avec le parrain",
                note="Présentation du mentor désigné, échange informel pour créer un lien de confiance.",
                date_deadline=start,
                user_id=self.coach_id.user_id.id,
            )
            weekly_checklist = [
                (7, "Semaine 1 : présentation informelle, tour des équipes, pause-café"),
                (14, "Semaine 2 : accompagnement lors d'une réunion d'équipe"),
                (21, "Semaine 3 : échange sur l'ambiance, les outils, les premiers ressentis"),
                (28, "Semaine 4 : préparation du bilan d'intégration avec RH"),
                (75, "Mois 2-3 : suivi ponctuel et échanges libres"),
            ]
            for days, summary in weekly_checklist:
                self.activity_schedule(
                    'mail.mail_activity_data_todo',
                    summary=summary,
                    note=_("Suivi du parrainage de %s. Pensez à relayer tout besoin au RH.", self.name),
                    date_deadline=start + timedelta(days=days),
                    user_id=self.coach_id.user_id.id,
                )

    # ------------------------------------------------------------------
    # Annexe 5 / Suivi & Evaluation : enquetes de satisfaction J+30 et J+90
    # ------------------------------------------------------------------
    @api.model
    def _cron_send_onboarding_satisfaction_survey(self):
        self._send_satisfaction_survey_batch(
            30, 'x_onboarding_survey_sent',
            'villa_nova_onboarding.survey_satisfaction_j30',
            'villa_nova_onboarding.mail_template_satisfaction_j30',
        )
        self._send_satisfaction_survey_batch(
            90, 'x_onboarding_survey_j90_sent',
            'villa_nova_onboarding.survey_satisfaction_j90',
            'villa_nova_onboarding.mail_template_satisfaction_j90',
        )

    @api.model
    def _send_satisfaction_survey_batch(self, days_offset, sent_field, survey_xmlid, template_xmlid):
        # '<=' plutot que '=' : si le cron ne tourne pas exactement le jour J
        # (conteneur arrete, etc.), les collaborateurs concernes sont rattrapes
        # au prochain passage au lieu d'etre definitivement oublies.
        target_date = fields.Date.context_today(self) - timedelta(days=days_offset)
        employees = self.search([
            ('joining_date', '!=', False),
            ('joining_date', '<=', target_date),
            (sent_field, '=', False),
            ('active', '=', True),
        ])
        survey = self.env.ref(survey_xmlid, raise_if_not_found=False)
        template = self.env.ref(template_xmlid, raise_if_not_found=False)
        if not survey:
            return
        for employee in employees:
            email = employee._get_onboarding_recipient_email()
            if not email:
                continue
            invite = self.env['survey.invite'].with_context(
                default_email_layout_xmlid='mail.mail_notification_light',
            ).create({
                'survey_id': survey.id,
                'emails': email,
                'template_id': template.id if template else False,
            })
            invite.action_invite()
            employee[sent_field] = True
