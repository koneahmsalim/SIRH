from odoo import http, _
from odoo.http import request
from odoo.addons.villa_nova_knowledge.controllers.portal import ItsmKnowledgePortal

MAX_ATTACHMENTS = 5
MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024  # 10 Mo


class ItsmPortalAdvanced(ItsmKnowledgePortal):
    """Phase 9 (Portail avance) : etend le controleur le plus derive deja
    en place (ItsmKnowledgePortal, Phase 8) plutot que de repartir de
    ItsmPortal - chaque route reimplementee integre donc deja la
    preselection de service etc. de la Phase 8, en plus des ajouts de
    cette phase (pieces jointes, SLA, articles suggeres)."""

    def _read_uploaded_files(self):
        """Lit les fichiers envoyes (max MAX_ATTACHMENTS, MAX_ATTACHMENT_SIZE
        chacun) et retourne (liste de tuples (nom, contenu) prete pour
        message_post/creation directe, liste d'erreurs de taille)."""
        files = request.httprequest.files.getlist('attachment')
        result, errors = [], []
        for file in files[:MAX_ATTACHMENTS]:
            if not file or not file.filename:
                continue
            content = file.read()
            if len(content) > MAX_ATTACHMENT_SIZE:
                errors.append(_("Le fichier « %(name)s » dépasse la taille maximale de 10 Mo.", name=file.filename))
                continue
            result.append((file.filename, content))
        return result, errors

    @http.route('/my/tickets/new', type='http', auth='user', website=True, methods=['GET', 'POST'])
    def portal_ticket_new(self, **post):
        services = request.env['itsm.service'].sudo().search([])
        selected_service_id = int(post['service_id']) if post.get('service_id') else False
        related_articles = request.env['itsm.kb.article']
        if selected_service_id:
            related_articles = request.env['itsm.kb.article'].sudo().search([
                ('related_service_ids', '=', selected_service_id),
                ('state', '=', 'published'), ('is_public', '=', True),
            ], limit=5)

        if request.httprequest.method == 'POST':
            subject = (post.get('subject') or '').strip()
            if not subject:
                return request.render('villa_nova_itsm.portal_ticket_new', {
                    'error': _("Merci d'indiquer un sujet."),
                    'values': post,
                    'services': services,
                    'selected_service_id': selected_service_id,
                    'related_articles': related_articles,
                })
            partner = request.env.user.partner_id
            ticket = request.env['itsm.ticket'].sudo().create({
                'subject': subject[:200],
                'description': (post.get('description') or '').strip(),
                'ticket_type': post.get('ticket_type') or 'service_request',
                'service_id': selected_service_id,
                'partner_id': partner.id,
                'employee_id': request.env['hr.employee'].sudo().search(
                    [('user_id', '=', request.env.user.id)], limit=1).id,
                'source': 'portal',
            })
            # Un fichier trop volumineux est simplement ignore (le ticket est
            # quand meme cree) plutot que de bloquer toute la soumission -
            # simplification deliberee, pas de mecanisme de message flash
            # sur ce portail pour signaler l'omission apres redirection.
            uploaded, _errors = self._read_uploaded_files()
            for name, content in uploaded:
                request.env['ir.attachment'].sudo().create({
                    'name': name,
                    'raw': content,
                    'res_model': 'itsm.ticket',
                    'res_id': ticket.id,
                })
            return request.redirect('/my/tickets/%s' % ticket.id)

        return request.render('villa_nova_itsm.portal_ticket_new', {
            'services': services,
            'selected_service_id': selected_service_id,
            'related_articles': related_articles,
        })

    @http.route('/my/tickets/<int:ticket_id>', type='http', auth='user', website=True)
    def portal_ticket_detail(self, ticket_id, **kw):
        try:
            ticket = self._itsm_get_ticket(ticket_id)
        except Exception:
            return request.redirect('/my')
        values = {
            'ticket': ticket,
            'page_name': 'ticket',
            'suggested_articles': ticket.suggested_kb_article_ids.filtered(
                lambda a: a.state == 'published' and a.is_public),
        }
        return request.render('villa_nova_itsm.portal_ticket_detail', values)

    @http.route('/my/tickets/<int:ticket_id>/message', type='http', auth='user', website=True, methods=['POST'])
    def portal_ticket_message(self, ticket_id, **post):
        ticket = self._itsm_get_ticket(ticket_id)
        body = (post.get('message') or '').strip()
        uploaded, _errors = self._read_uploaded_files()
        if body or uploaded:
            ticket.message_post(
                body=body or _("(Pièce jointe sans commentaire)"), message_type='comment',
                subtype_xmlid='mail.mt_comment', author_id=request.env.user.partner_id.id,
                attachments=uploaded,
            )
        return request.redirect('/my/tickets/%s' % ticket_id)
