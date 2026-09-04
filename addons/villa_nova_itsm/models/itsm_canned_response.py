from odoo import fields, models


class ItsmCannedResponse(models.Model):
    _name = 'itsm.canned.response'
    _description = "Réponse prédéfinie"
    _order = 'name'

    name = fields.Char(string="Nom", required=True)
    content = fields.Html(required=True)
    category_id = fields.Many2one('itsm.category', string="Catégorie")
