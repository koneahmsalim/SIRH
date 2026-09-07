from odoo import models


class ItsmService(models.Model):
    _name = 'itsm.service'
    _inherit = ['itsm.service', 'cmdb.ci.mixin']
