import html

from odoo import http
from odoo.http import request

# Equivalent des Forms Asana : Odoo n'a d'intake public que par email (alias
# de projet) - ici un vrai formulaire web, sans compte requis. Le projet est
# retrouve par (id, access_token) - le token natif du mixin portal.mixin
# deja porte par project.project, pas un champ maison - donc pas devinable
# et revocable comme n'importe quel lien de partage Odoo.
MAX_NAME = 200
MAX_TEXT = 5000
MAX_CONTACT = 120


class VillaNovaProjectPublicForm(http.Controller):

    def _get_project(self, project_id, token):
        project = request.env['project.project'].sudo().browse(project_id).exists()
        if not project or not project.access_token or project.access_token != token:
            return None
        return project

    @http.route('/projet/formulaire/<int:project_id>/<string:token>', type='http', auth='public', website=True, sitemap=False)
    def project_public_form(self, project_id, token, **kwargs):
        project = self._get_project(project_id, token)
        if not project:
            return request.not_found()
        return request.render('villa_nova_project.public_task_form', {'project': project})

    @http.route('/projet/formulaire/<int:project_id>/<string:token>/soumettre', type='http', auth='public',
                website=True, methods=['POST'], csrf=True, sitemap=False)
    def project_public_form_submit(self, project_id, token, **post):
        project = self._get_project(project_id, token)
        if not project:
            return request.not_found()

        # Piege a robots : champ cache qui doit rester vide pour un humain.
        if post.get('website'):
            return request.redirect('/projet/formulaire/%d/%s/merci' % (project_id, token))

        name = (post.get('name') or '').strip()[:MAX_NAME]
        if not name:
            return request.render('villa_nova_project.public_task_form', {
                'project': project,
                'error': "Merci d'indiquer un titre pour votre demande.",
                'values': post,
            })

        requester_name = (post.get('requester_name') or '').strip()[:MAX_CONTACT]
        requester_email = (post.get('requester_email') or '').strip()[:MAX_CONTACT]
        details = (post.get('description') or '').strip()[:MAX_TEXT]

        description_lines = []
        who = requester_name or "un visiteur"
        contact = " (%s)" % requester_email if requester_email else ""
        description_lines.append("Demande soumise via le formulaire public par %s%s." % (who, contact))
        if details:
            description_lines.append("")
            description_lines.extend(details.splitlines())

        description_html = '<br/>'.join(html.escape(line) for line in description_lines)

        # Sans ce user_ids explicite, la tache herite par defaut de
        # l'utilisateur courant de la requete - ici le visiteur anonyme
        # (l'utilisateur technique "Public user" d'Odoo), pas quelqu'un de
        # l'equipe : la demande doit arriver non assignee, a trier.
        request.env['project.task'].sudo().create({
            'name': name,
            'project_id': project.id,
            'description': description_html,
            'user_ids': [(6, 0, [])],
        })

        return request.redirect('/projet/formulaire/%d/%s/merci' % (project_id, token))

    @http.route('/projet/formulaire/<int:project_id>/<string:token>/merci', type='http', auth='public', website=True, sitemap=False)
    def project_public_form_thanks(self, project_id, token, **kwargs):
        project = self._get_project(project_id, token)
        if not project:
            return request.not_found()
        return request.render('villa_nova_project.public_task_form_thanks', {'project': project})
