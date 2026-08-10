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
