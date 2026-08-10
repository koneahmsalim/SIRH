from datetime import timedelta

from odoo import _, fields, models


class HrApplicant(models.Model):
    _inherit = 'hr.applicant'

    def action_villa_nova_send_prequalification_test(self):
        """Envoie automatiquement le test de prequalification en ligne des que la
        candidature atteint l'etape correspondante (Etape 3 de la procedure RH),
        sans intervention manuelle de la RH."""
        for applicant in self:
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
                'activity_summary': _("Appeler le candidat (préqualification téléphonique)"),
                'assignees': lambda applicant: applicant.job_id.user_id,
            },
            ref('hr_recruitment.stage_job3').id: {
                'template_xmlid': 'villa_nova_recruitment.mail_template_entretien_structure',
                'activity_summary': _("Organiser l'entretien structuré (RH / Technique / Pratique)"),
                'assignees': lambda applicant: applicant.job_id.manager_id or applicant.job_id.user_id,
            },
            ref('villa_nova_recruitment.stage_tests_pratiques').id: {
                'template_xmlid': 'villa_nova_recruitment.mail_template_tests_pratiques',
                'activity_summary': _("Administrer les tests pratiques"),
                'assignees': lambda applicant: applicant.job_id.manager_id or applicant.job_id.user_id,
            },
            ref('villa_nova_recruitment.stage_entretien_president').id: {
                'template_xmlid': 'villa_nova_recruitment.mail_template_entretien_president',
                'activity_summary': _("Réaliser l'entretien avec le Président"),
                'assignees': lambda applicant: applicant._get_direction_generale_users(),
            },
            ref('villa_nova_recruitment.stage_verification_references').id: {
                'template_xmlid': 'villa_nova_recruitment.mail_template_verification_references',
                'activity_summary': _("Vérifier les références professionnelles du candidat"),
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
                    'mail.mail_activity_data_todo',
                    summary=config['activity_summary'],
                    user_id=user.id,
                )
