from odoo import http, fields, _
from odoo.exceptions import AccessError, MissingError
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager


class ItsmPortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'ticket_count' in counters:
            values['ticket_count'] = request.env['itsm.ticket'].search_count(self._itsm_ticket_domain())
        return values

    def _itsm_ticket_domain(self):
        partner = request.env.user.partner_id
        return ['|', ('partner_id', '=', partner.id), ('message_partner_ids', 'in', [partner.id])]

    @http.route(['/my/tickets', '/my/tickets/page/<int:page>'], type='http', auth='user', website=True)
    def portal_my_tickets(self, page=1, sortby=None, filterby=None, **kw):
        Ticket = request.env['itsm.ticket']
        domain = self._itsm_ticket_domain()

        searchbar_filters = {
            'all': {'label': _("Toutes"), 'domain': []},
            'open': {'label': _("Ouvertes"), 'domain': [('state', 'not in', ['resolved', 'closed', 'cancelled'])]},
            'closed': {'label': _("Clôturées"), 'domain': [('state', 'in', ['resolved', 'closed'])]},
        }
        filterby = filterby or 'all'
        domain += searchbar_filters[filterby]['domain']

        searchbar_sortings = {
            'date': {'label': _("Date"), 'order': 'create_date desc'},
            'name': {'label': _("Référence"), 'order': 'name'},
            'state': {'label': _("Statut"), 'order': 'state'},
        }
        sortby = sortby or 'date'
        order = searchbar_sortings[sortby]['order']

        ticket_count = Ticket.search_count(domain)
        pager = portal_pager(
            url="/my/tickets", url_args={'sortby': sortby, 'filterby': filterby},
            total=ticket_count, page=page, step=self._items_per_page,
        )
        tickets = Ticket.search(domain, order=order, limit=self._items_per_page, offset=pager['offset'])

        values = self._prepare_portal_layout_values()
        values.update({
            'tickets': tickets,
            'page_name': 'ticket',
            'pager': pager,
            'searchbar_sortings': searchbar_sortings,
            'searchbar_filters': searchbar_filters,
            'sortby': sortby,
            'filterby': filterby,
            'default_url': '/my/tickets',
        })
        return request.render('villa_nova_itsm.portal_my_tickets', values)

    @http.route('/my/tickets/new', type='http', auth='user', website=True, methods=['GET', 'POST'])
    def portal_ticket_new(self, **post):
        if request.httprequest.method == 'POST':
            subject = (post.get('subject') or '').strip()
            if not subject:
                return request.render('villa_nova_itsm.portal_ticket_new', {
                    'error': _("Merci d'indiquer un sujet."),
                    'values': post,
                    'services': request.env['itsm.service'].sudo().search([]),
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
        return request.render('villa_nova_itsm.portal_ticket_new', {
            'services': request.env['itsm.service'].sudo().search([]),
        })

    def _itsm_get_ticket(self, ticket_id):
        ticket = request.env['itsm.ticket'].search([('id', '=', ticket_id)])
        if not ticket:
            raise MissingError(_("Ce ticket n'existe pas."))
        return ticket

    @http.route('/my/tickets/<int:ticket_id>', type='http', auth='user', website=True)
    def portal_ticket_detail(self, ticket_id, **kw):
        try:
            ticket = self._itsm_get_ticket(ticket_id)
        except (AccessError, MissingError):
            return request.redirect('/my')
        values = {
            'ticket': ticket,
            'page_name': 'ticket',
        }
        return request.render('villa_nova_itsm.portal_ticket_detail', values)

    @http.route('/my/tickets/<int:ticket_id>/message', type='http', auth='user', website=True, methods=['POST'])
    def portal_ticket_message(self, ticket_id, **post):
        ticket = self._itsm_get_ticket(ticket_id)
        body = (post.get('message') or '').strip()
        if body:
            ticket.message_post(
                body=body, message_type='comment', subtype_xmlid='mail.mt_comment',
                author_id=request.env.user.partner_id.id,
            )
        return request.redirect('/my/tickets/%s' % ticket_id)

    @http.route('/my/tickets/<int:ticket_id>/rate', type='http', auth='user', website=True, methods=['POST'])
    def portal_ticket_rate(self, ticket_id, rating=None, **post):
        ticket = self._itsm_get_ticket(ticket_id)
        if rating in ('great', 'okay', 'bad'):
            ticket.sudo().write({'satisfaction_rating': rating})
        return request.redirect('/my/tickets/%s' % ticket_id)
