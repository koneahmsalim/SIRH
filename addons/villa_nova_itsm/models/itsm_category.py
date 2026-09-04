from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ItsmCategory(models.Model):
    """Categorie / sous-categorie (parent_id auto-referent, comme les
    categories de depenses natives) - ex. "Matériel > Ordinateur portable".
    Sert deja de point d'accroche pour le futur Service Catalog (Phase 8) :
    un service pourra pointer vers une categorie plutot que l'inverse."""
    _name = 'itsm.category'
    _description = "Catégorie de ticket ITSM"
    _order = 'complete_name'
    _parent_store = True

    name = fields.Char(string="Nom", required=True, translate=True)
    parent_id = fields.Many2one('itsm.category', string="Catégorie parente", index=True, ondelete='cascade')
    parent_path = fields.Char(index=True, unaccent=False)
    child_ids = fields.One2many('itsm.category', 'parent_id', string="Sous-catégories")
    complete_name = fields.Char(compute='_compute_complete_name', store=True, recursive=True)
    active = fields.Boolean(default=True)
    default_team_id = fields.Many2one('itsm.team', string="Équipe par défaut")
    default_sla_policy_id = fields.Many2one('itsm.sla.policy', string="SLA par défaut")
    ticket_count = fields.Integer(compute='_compute_ticket_count')

    @api.depends('name', 'parent_id.complete_name')
    def _compute_complete_name(self):
        for category in self:
            if category.parent_id:
                category.complete_name = '%s / %s' % (category.parent_id.complete_name, category.name)
            else:
                category.complete_name = category.name

    def _compute_ticket_count(self):
        Ticket = self.env['itsm.ticket']
        for category in self:
            category.ticket_count = Ticket.search_count([('category_id', '=', category.id)])

    @api.constrains('parent_id')
    def _check_category_recursion(self):
        if self._has_cycle():
            raise ValidationError("Impossible de créer une hiérarchie de catégories récursive.")
