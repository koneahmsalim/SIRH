from odoo import http, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import pager as portal_pager
from odoo.addons.villa_nova_itsm.controllers.portal import ItsmPortal


class ItsmKnowledgePortal(ItsmPortal):

    @http.route(['/selfservice'], type='http', auth='user', website=True)
    def portal_selfservice_home(self, **kw):
        values = self._prepare_portal_layout_values()
        values.update({
            'page_name': 'selfservice',
            'ticket_count': request.env['itsm.ticket'].sudo().search_count(self._itsm_ticket_domain()),
            'article_count': request.env['itsm.kb.article'].sudo().search_count(
                [('state', '=', 'published'), ('is_public', '=', True)]),
            'service_count': request.env['itsm.service'].sudo().search_count([]),
        })
        return request.render('villa_nova_knowledge.portal_selfservice_home', values)

    @http.route(['/my/knowledge', '/my/knowledge/page/<int:page>'], type='http', auth='user', website=True)
    def portal_knowledge(self, page=1, search=None, category_id=None, **kw):
        Article = request.env['itsm.kb.article'].sudo()
        domain = [('state', '=', 'published'), ('is_public', '=', True)]
        if search:
            domain += ['|', ('name', 'ilike', search), ('content', 'ilike', search)]
        if category_id:
            domain += [('category_id', '=', int(category_id))]

        article_count = Article.search_count(domain)
        pager = portal_pager(
            url="/my/knowledge", url_args={'search': search, 'category_id': category_id},
            total=article_count, page=page, step=self._items_per_page,
        )
        articles = Article.search(domain, limit=self._items_per_page, offset=pager['offset'])

        values = self._prepare_portal_layout_values()
        values.update({
            'articles': articles,
            'page_name': 'knowledge',
            'pager': pager,
            'search': search or '',
            'category_id': int(category_id) if category_id else False,
            'categories': request.env['itsm.category'].sudo().search([]),
        })
        return request.render('villa_nova_knowledge.portal_knowledge_list', values)

    def _get_public_article(self, article_id):
        return request.env['itsm.kb.article'].sudo().search([
            ('id', '=', article_id), ('state', '=', 'published'), ('is_public', '=', True),
        ], limit=1)

    @http.route('/my/knowledge/<int:article_id>', type='http', auth='user', website=True)
    def portal_knowledge_detail(self, article_id, **kw):
        article = self._get_public_article(article_id)
        if not article:
            return request.redirect('/my/knowledge')
        article.action_register_view()
        values = {'article': article, 'page_name': 'knowledge'}
        return request.render('villa_nova_knowledge.portal_knowledge_detail', values)

    @http.route('/my/knowledge/<int:article_id>/vote', type='http', auth='user', website=True, methods=['POST'])
    def portal_knowledge_vote(self, article_id, helpful=None, **post):
        article = self._get_public_article(article_id)
        if article:
            if helpful == '1':
                article.action_mark_helpful()
            else:
                article.action_mark_not_helpful()
        return request.redirect('/my/knowledge/%s' % article_id)

    @http.route(['/my/services'], type='http', auth='user', website=True)
    def portal_services(self, **kw):
        services = request.env['itsm.service'].sudo().search([])
        values = self._prepare_portal_layout_values()
        values.update({'services': services, 'page_name': 'services'})
        return request.render('villa_nova_knowledge.portal_services_catalog', values)

    @http.route('/my/tickets/new', type='http', auth='user', website=True, methods=['GET', 'POST'])
    def portal_ticket_new(self, **post):
        """Surcharge complete (pas d'injection partielle dans la reponse
        du parent) pour ajouter la preselection du service depuis le
        catalogue - le reste du comportement (validation, creation) est
        identique a la version Phase 1."""
        services = request.env['itsm.service'].sudo().search([])
        if request.httprequest.method == 'POST':
            subject = (post.get('subject') or '').strip()
            if not subject:
                return request.render('villa_nova_itsm.portal_ticket_new', {
                    'error': _("Merci d'indiquer un sujet."),
                    'values': post,
                    'services': services,
                    'selected_service_id': int(post['service_id']) if post.get('service_id') else False,
                })
            partner = request.env.user.partner_id
            ticket = request.env['itsm.ticket'].sudo().create({
                'subject': subject[:200],
                'description': (post.get('description') or '').strip(),
                'ticket_type': post.get('ticket_type') or 'service_request',
                'service_id': int(post['service_id']) if post.get('service_id') else False,
                'partner_id': partner.id,
                'employee_id': request.env['hr.employee'].sudo().search(
                    [('user_id', '=', request.env.user.id)], limit=1).id,
                'source': 'portal',
            })
            return request.redirect('/my/tickets/%s' % ticket.id)
        selected_service_id = int(post['service_id']) if post.get('service_id') else False
        return request.render('villa_nova_itsm.portal_ticket_new', {
            'services': services,
            'selected_service_id': selected_service_id,
        })
