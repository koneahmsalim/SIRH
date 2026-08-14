from odoo import http
from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.addons.website_hr_recruitment.controllers.main import WebsiteHrRecruitment
from odoo.http import request


class VillaNovaWebsiteHrRecruitment(WebsiteHrRecruitment):

    # Un compte (portail) est desormais obligatoire pour postuler : la route
    # passe en auth="user", ce qui redirige automatiquement un visiteur non
    # connecte vers la page de connexion/creation de compte, puis le ramene
    # ici une fois authentifie (mecanisme natif Odoo, aucun code supplementaire
    # necessaire pour ce redirect).
    @http.route('''/jobs/apply/<model("hr.job"):job>''', type='http', auth='user', website=True, sitemap=True)
    def jobs_apply(self, job, **kwargs):
        return super().jobs_apply(job, **kwargs)

    def extract_data(self, model, values):
        data = super().extract_data(model, values)
        if model.sudo().model == 'hr.applicant' and not request.env.user._is_public():
            candidate_id = data.get('record', {}).get('candidate_id')
            if candidate_id:
                candidate = request.env['hr.candidate'].sudo().browse(candidate_id)
                if not candidate.partner_id:
                    candidate.partner_id = request.env.user.partner_id
        return data


class VillaNovaRecruitmentPortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'applications_count' in counters:
            values['applications_count'] = request.env['hr.applicant'].search_count([])
        return values

    def _get_own_applicants(self):
        return request.env['hr.applicant'].search([], order='create_date desc')

    @http.route('/my/applications', type='http', auth='user', website=True)
    def portal_my_applications(self, **kwargs):
        applicants = self._get_own_applicants()
        values = {
            'applicants': applicants,
            'page_name': 'applications',
            'x_job_alert_subscribed': request.env.user.partner_id.x_job_alert_subscribed,
        }
        return request.render('villa_nova_recruitment.portal_my_applications', values)

    @http.route('/my/applications/<int:applicant_id>', type='http', auth='user', website=True)
    def portal_application_detail(self, applicant_id, **kwargs):
        applicant = request.env['hr.applicant'].search([('id', '=', applicant_id)], limit=1)
        if not applicant:
            return request.not_found()
        stages = request.env['hr.recruitment.stage'].sudo().search([], order='sequence')
        values = {
            'applicant': applicant,
            'stages': stages,
            'page_name': 'applications',
        }
        return request.render('villa_nova_recruitment.portal_application_detail', values)

    @http.route('/my/job-alerts/toggle', type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def portal_toggle_job_alert(self, **kwargs):
        partner = request.env.user.partner_id
        partner.x_job_alert_subscribed = not partner.x_job_alert_subscribed
        return request.redirect('/my/applications')
