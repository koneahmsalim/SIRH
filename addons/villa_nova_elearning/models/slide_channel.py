from odoo import api, models

STATUS_ORDER = {'ongoing': 0, 'joined': 1, 'completed': 2}


class SlideChannelPartner(models.Model):
    _inherit = 'slide.channel.partner'

    @api.model
    def get_villa_nova_my_trainings(self):
        """Formations de l'utilisateur courant, triees pour mettre en avant
        ce qui reste a faire (en cours puis a demarrer) avant les formations
        deja terminees - lecture "qu'est-ce qu'il me reste a faire" plutot
        qu'un simple catalogue neutre."""
        partner = self.env.user.partner_id
        enrollments = self.search([('partner_id', '=', partner.id)])
        result = []
        for enrollment in enrollments:
            channel = enrollment.channel_id
            result.append({
                'channel_id': channel.id,
                'name': channel.name,
                'completion': enrollment.completion,
                'member_status': enrollment.member_status,
                'total_slides': len(channel.slide_ids.filtered(lambda s: not s.is_category)),
                'completed_slides': enrollment.completed_slides_count,
                'website_url': channel.website_url,
            })
        result.sort(key=lambda r: (STATUS_ORDER.get(r['member_status'], 1), -r['completion']))
        return result
