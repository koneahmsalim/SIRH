from odoo import models


class HrApplicant(models.Model):
    _inherit = 'hr.applicant'

    def action_villa_nova_process_hiring(self):
        """Etend l'Etape 6 du recrutement (creation de la fiche employe) pour
        enchainer automatiquement sur la checklist pre-onboarding (Annexe
        Onboarding Villa Nova)."""
        res = super().action_villa_nova_process_hiring()
        for applicant in self:
            employee = applicant.employee_id
            if not employee or employee.x_onboarding_started:
                continue
            if applicant.availability and not employee.joining_date:
                employee.joining_date = applicant.availability
            if applicant.email_from and not employee.private_email:
                employee.private_email = applicant.email_from
            employee.action_villa_nova_start_onboarding()
        return res
