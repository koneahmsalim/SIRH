from odoo import _, api, fields, models

STATE_SELECTION = [
    ('draft', "Brouillon"),
    ('published', "Publié"),
    ('archived', "Archivé"),
]


class ItsmKbArticle(models.Model):
    _name = 'itsm.kb.article'
    _description = "Article de la base de connaissances"
    _inherit = ['mail.thread']
    _order = 'name'

    name = fields.Char(string="Titre", required=True, tracking=True)
    content = fields.Html(string="Contenu")
    category_id = fields.Many2one('itsm.category', string="Catégorie")
    tag_ids = fields.Many2many('itsm.tag', string="Étiquettes")
    state = fields.Selection(STATE_SELECTION, string="Statut", default='draft', required=True, tracking=True)
    is_public = fields.Boolean(
        string="Visible sur le portail", default=False,
        help="Visible par les clients sur le portail self-service, en plus d'être publié en interne.",
    )
    author_id = fields.Many2one('res.users', string="Auteur", default=lambda self: self.env.user)

    view_count = fields.Integer(string="Vues", default=0, copy=False)
    helpful_count = fields.Integer(string="Utile", default=0, copy=False)
    not_helpful_count = fields.Integer(string="Pas utile", default=0, copy=False)
    helpful_ratio = fields.Float(string="Taux d'utilité", compute='_compute_helpful_ratio', store=True)

    related_service_ids = fields.Many2many('itsm.service', string="Services liés")
    ticket_ids = fields.Many2many(
        'itsm.ticket', 'itsm_ticket_kb_article_rel', 'article_id', 'ticket_id', string="Tickets liés",
    )
    ticket_count = fields.Integer(string="Nombre de tickets liés", compute='_compute_ticket_count')

    @api.depends('helpful_count', 'not_helpful_count')
    def _compute_helpful_ratio(self):
        for article in self:
            total = article.helpful_count + article.not_helpful_count
            article.helpful_ratio = (article.helpful_count / total) if total else 0.0

    @api.depends('ticket_ids')
    def _compute_ticket_count(self):
        for article in self:
            article.ticket_count = len(article.ticket_ids)

    def action_publish(self):
        self.write({'state': 'published'})

    def action_archive_article(self):
        self.write({'state': 'archived'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})

    def action_register_view(self):
        """Incremente le compteur de vues - appele quand un agent ouvre la
        fiche ou qu'un visiteur du portail consulte l'article publie."""
        for article in self:
            article.sudo().view_count += 1

    def action_mark_helpful(self):
        for article in self:
            article.sudo().helpful_count += 1

    def action_mark_not_helpful(self):
        for article in self:
            article.sudo().not_helpful_count += 1
