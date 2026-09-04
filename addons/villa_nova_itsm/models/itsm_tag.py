from odoo import fields, models


class ItsmTag(models.Model):
    _name = 'itsm.tag'
    _description = "Étiquette de ticket ITSM"
    _order = 'name'

    name = fields.Char(string="Nom", required=True)
    color = fields.Integer(string="Couleur")

    _sql_constraints = [
        ('name_uniq', 'unique (name)', "Cette étiquette existe déjà."),
    ]
