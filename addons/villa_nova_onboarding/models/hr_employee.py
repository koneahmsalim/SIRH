from datetime import timedelta

from odoo import _, api, fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    x_onboarding_started = fields.Boolean(string="Onboarding démarré", copy=False)
    x_onboarding_survey_sent = fields.Boolean(string="Enquête J+30 envoyée", copy=False)

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
        newly_assigned = self.env['hr.employee']
        if 'coach_id' in vals and vals.get('coach_id'):
            newly_assigned = self.filtered(lambda e: not e.coach_id)
        res = super().write(vals)
        for employee in newly_assigned:
            employee._action_villa_nova_coach_assigned()
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
    # Annexe 5 : Enquete de satisfaction J+30
    # ------------------------------------------------------------------
    @api.model
    def _cron_send_onboarding_satisfaction_survey(self):
        target_date = fields.Date.context_today(self) - timedelta(days=30)
        employees = self.search([
            ('joining_date', '=', target_date),
            ('x_onboarding_survey_sent', '=', False),
            ('active', '=', True),
        ])
        survey = self.env.ref('villa_nova_onboarding.survey_satisfaction_j30', raise_if_not_found=False)
        template = self.env.ref(
            'villa_nova_onboarding.mail_template_satisfaction_j30', raise_if_not_found=False,
        )
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
            employee.x_onboarding_survey_sent = True
