from datetime import timedelta

from odoo import _, api, fields, models

# Delai de grace avant l'envoi effectif d'un email/test au candidat suite a un
# changement d'etape : protege contre un glisser-deposer accidentel dans le
# kanban (la RH a le temps de corriger avant qu'une communication ne parte).
NOTIFICATION_GRACE_DELAY = timedelta(minutes=15)


class HrApplicant(models.Model):
    _inherit = 'hr.applicant'

    x_pending_notification_stage_id = fields.Many2one(
        'hr.recruitment.stage',
        string="Étape en attente de notification",
        copy=False,
        help="Etape enregistree au moment du glisser-depose, utilisee pour verifier "
             "que le candidat est toujours a cette etape avant d'envoyer la notification.",
    )
    x_notify_after = fields.Datetime(
        string="Notifier le candidat après le",
        copy=False,
        help="Tant que cette date n'est pas atteinte, aucune communication n'est envoyee "
             "au candidat : cela laisse le temps d'annuler un glisser-depose accidentel.",
    )

    def action_villa_nova_schedule_notification(self):
        """Declenchee immediatement au changement d'etape (glisser-depose inclus) :
        n'envoie rien tout de suite, se contente de programmer l'envoi apres un
        delai de grace. Si la carte est redeplacee entre-temps, rien ne part."""
        for applicant in self:
            applicant.write({
                'x_pending_notification_stage_id': applicant.stage_id.id,
                'x_notify_after': fields.Datetime.now() + NOTIFICATION_GRACE_DELAY,
            })

    @api.model
    def _cron_process_pending_stage_notifications(self):
        to_process = self.search([
            ('x_notify_after', '!=', False),
            ('x_notify_after', '<=', fields.Datetime.now()),
        ])
        for applicant in to_process:
            pending_stage = applicant.x_pending_notification_stage_id
            applicant.write({
                'x_pending_notification_stage_id': False,
                'x_notify_after': False,
            })
            if not pending_stage or applicant.stage_id != pending_stage:
                # La carte a ete redeplacee entretemps (correction d'un glisser
                # accidentel) : on n'envoie rien, pas de faux espoir au candidat.
                continue
            applicant.action_villa_nova_send_prequalification_test()
            applicant.action_villa_nova_notify_stage()

    def action_villa_nova_send_prequalification_test(self):
        """Envoie le test de prequalification en ligne (Etape 3 de la procedure RH),
        uniquement si le candidat est bien toujours a l'etape correspondante."""
        stage_test = self.env.ref(
            'villa_nova_recruitment.stage_test_prequalification', raise_if_not_found=False,
        )
        for applicant in self:
            if stage_test and applicant.stage_id != stage_test:
                continue
            if not applicant.survey_id or applicant.response_ids:
                continue
            if not applicant.partner_id:
                if not applicant.partner_name:
                    continue
                applicant.partner_id = self.env['res.partner'].sudo().create({
                    'is_company': False,
                    'name': applicant.partner_name,
                    'email': applicant.email_from,
                    'phone': applicant.partner_phone,
                })
            template = self.env.ref(
                'hr_recruitment_survey.mail_template_applicant_interview_invite',
                raise_if_not_found=False,
            )
            invite = self.env['survey.invite'].with_context(
                default_email_layout_xmlid='mail.mail_notification_light',
            ).create({
                'applicant_id': applicant.id,
                'survey_id': applicant.survey_id.id,
                'partner_ids': [(6, 0, applicant.partner_id.ids)],
                'template_id': template.id if template else False,
                'deadline': fields.Datetime.now() + timedelta(days=15),
            })
            invite.action_invite()

    def _get_stage_notification_config(self):
        """Etape 4 et 5 : email automatique au candidat + tache assignee a la
        bonne personne (manager, RH ou Direction Generale) a chaque etape."""
        ref = self.env.ref
        return {
            ref('hr_recruitment.stage_job2').id: {
                'template_xmlid': 'villa_nova_recruitment.mail_template_prequalification_telephonique',
                'activity_summary': _("Planifier l'appel de préqualification téléphonique"),
                'activity_type_xmlid': 'mail.mail_activity_data_meeting',
                'assignees': lambda applicant: applicant.job_id.user_id,
            },
            ref('hr_recruitment.stage_job3').id: {
                'template_xmlid': 'villa_nova_recruitment.mail_template_entretien_structure',
                'activity_summary': _("Organiser l'entretien structuré (RH / Technique / Pratique)"),
                'activity_type_xmlid': 'mail.mail_activity_data_meeting',
                'assignees': lambda applicant: applicant.job_id.manager_id or applicant.job_id.user_id,
            },
            ref('villa_nova_recruitment.stage_tests_pratiques').id: {
                'template_xmlid': 'villa_nova_recruitment.mail_template_tests_pratiques',
                'activity_summary': _("Planifier et administrer les tests pratiques"),
                'activity_type_xmlid': 'mail.mail_activity_data_meeting',
                'assignees': lambda applicant: applicant.job_id.manager_id or applicant.job_id.user_id,
            },
            ref('villa_nova_recruitment.stage_entretien_president').id: {
                'template_xmlid': 'villa_nova_recruitment.mail_template_entretien_president',
                'activity_summary': _("Planifier l'entretien avec le Président"),
                'activity_type_xmlid': 'mail.mail_activity_data_meeting',
                'assignees': lambda applicant: applicant._get_direction_generale_users(),
            },
            ref('villa_nova_recruitment.stage_verification_references').id: {
                'template_xmlid': 'villa_nova_recruitment.mail_template_verification_references',
                'activity_summary': _("Vérifier les références professionnelles du candidat"),
                'activity_type_xmlid': 'mail.mail_activity_data_call',
                'assignees': lambda applicant: applicant.job_id.user_id,
            },
        }

    def _get_direction_generale_users(self):
        group = self.env.ref(
            'villa_nova_recruitment.group_direction_generale', raise_if_not_found=False,
        )
        return group.users if group else self.env['res.users']

    def action_villa_nova_notify_stage(self):
        config_map = self._get_stage_notification_config()
        for applicant in self:
            config = config_map.get(applicant.stage_id.id)
            if not config:
                continue

            if applicant.email_from:
                template = self.env.ref(config['template_xmlid'], raise_if_not_found=False)
                if template:
                    template.send_mail(applicant.id, force_send=True)

            for user in config['assignees'](applicant):
                applicant.activity_schedule(
                    config.get('activity_type_xmlid', 'mail.mail_activity_data_todo'),
                    summary=config['activity_summary'],
                    user_id=user.id,
                )
