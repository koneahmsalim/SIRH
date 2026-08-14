from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    x_job_alert_subscribed = fields.Boolean(
        string="Alertes nouveaux postes",
        help="Reçoit un email lorsqu'un nouveau poste est publié sur le site.",
    )
