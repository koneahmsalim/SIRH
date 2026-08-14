from odoo import http
from odoo.http import request


class VillaNovaRecruitmentTracking(http.Controller):

    @http.route('/jobs/my/application/<string:token>', type='http', auth='public', website=True, sitemap=False)
    def track_application(self, token, **kwargs):
        # Recherche strictement par jeton (jamais par id/email) pour eviter
        # toute enumeration ; sudo() car un visiteur public n'a aucun droit
        # natif sur hr.applicant, mais cette route ne fait que lire une seule
        # candidature ciblee par un jeton non devinable.
        applicant = request.env['hr.applicant'].sudo().search([('access_token', '=', token)], limit=1)
        if not applicant:
            return request.render('villa_nova_recruitment.application_tracking_not_found')

        stages = request.env['hr.recruitment.stage'].sudo().search([], order='sequence')
        return request.render('villa_nova_recruitment.application_tracking', {
            'applicant': applicant,
            'stages': stages,
        })
