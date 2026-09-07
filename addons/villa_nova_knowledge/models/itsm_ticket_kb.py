from odoo import api, fields, models


class ItsmTicket(models.Model):
    """Articles utilises pour resoudre ce ticket - ajoute via _inherit
    depuis ce module, meme architecture que equipment_id/problem_id."""
    _inherit = 'itsm.ticket'

    kb_article_ids = fields.Many2many(
        'itsm.kb.article', 'itsm_ticket_kb_article_rel', 'ticket_id', 'article_id',
        string="Articles utilisés",
    )
    suggested_kb_article_ids = fields.Many2many(
        'itsm.kb.article', string="Articles suggérés", compute='_compute_suggested_kb_articles',
    )

    @api.depends('category_id')
    def _compute_suggested_kb_articles(self):
        Article = self.env['itsm.kb.article']
        for ticket in self:
            if not ticket.category_id:
                ticket.suggested_kb_article_ids = Article.browse()
                continue
            ticket.suggested_kb_article_ids = Article.search([
                ('category_id', '=', ticket.category_id.id),
                ('state', '=', 'published'),
            ], limit=5)
