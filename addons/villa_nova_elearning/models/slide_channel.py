from odoo import api, fields, models

STATUS_ORDER = {'ongoing': 0, 'joined': 1, 'completed': 2}


class SlideChannelPartner(models.Model):
    _inherit = 'slide.channel.partner'

    villa_nova_mandatory = fields.Boolean(
        string="Obligatoire", help="Formation assignée par la RH, à suivre obligatoirement.")
    villa_nova_assigned_by = fields.Many2one('res.users', string="Assignée par")
    villa_nova_due_date = fields.Date(string="Échéance")

    @api.model
    def get_villa_nova_my_trainings(self):
        """Formations de l'utilisateur courant, triees pour mettre en avant
        ce qui reste a faire (obligatoire d'abord, puis en cours, puis a
        demarrer) avant les formations deja terminees - lecture "qu'est-ce
        qu'il me reste a faire" plutot qu'un simple catalogue neutre.

        sudo() necessaire : slide.channel.partner est ferme par defaut a
        tout le monde sauf le groupe eLearning/Officer (cf. restriction
        volontaire posee par ce module sur ce groupe, voir hooks.py) - un
        simple utilisateur ne peut nativement pas lire ses propres
        inscriptions depuis le backend (seul le portail web le permet, via
        des controleurs qui font deja ce sudo() a un autre niveau). Sans
        danger ici : le domaine est fige sur l'utilisateur courant, jamais
        parametrable depuis le client."""
        partner = self.env.user.partner_id
        enrollments = self.sudo().search([('partner_id', '=', partner.id)])
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
                'mandatory': enrollment.villa_nova_mandatory,
                'due_date': fields.Date.to_string(enrollment.villa_nova_due_date) if enrollment.villa_nova_due_date else False,
            })
        result.sort(key=lambda r: (
            not r['mandatory'],
            STATUS_ORDER.get(r['member_status'], 1),
            -r['completion'],
        ))
        return result
