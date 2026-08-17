from odoo import api, fields, models
from odoo.exceptions import ValidationError


class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    villa_nova_activity_id = fields.Many2one(
        'villa.nova.timesheet.activity', string="Code activité",
        domain="[('id', 'in', villa_nova_allowed_activity_ids)]",
        help="Nomenclature IAG : détermine la facturabilité par défaut et si un projet est obligatoire.",
    )
    villa_nova_allowed_activity_ids = fields.Many2many(
        'villa.nova.timesheet.activity', compute='_compute_villa_nova_allowed_activity_ids',
        string="Codes disponibles pour cet employé",
    )
    villa_nova_billability = fields.Selection(
        related='villa_nova_activity_id.billability_default', string="Facturabilité",
        store=True, readonly=True,
    )

    @api.depends('employee_id')
    def _compute_villa_nova_allowed_activity_ids(self):
        Activity = self.env['villa.nova.timesheet.activity']
        for line in self:
            if line.employee_id:
                line.villa_nova_allowed_activity_ids = Activity._get_available_for_employee(line.employee_id)
            else:
                line.villa_nova_allowed_activity_ids = Activity.search([('visibility_scope', '=', 'all')])

    @api.constrains('villa_nova_activity_id', 'project_id')
    def _check_villa_nova_project_required(self):
        for line in self:
            activity = line.villa_nova_activity_id
            if activity and activity.project_required == 'oui' and not line.project_id:
                raise ValidationError(
                    "Le code activité [%s] %s exige obligatoirement un projet / mandat / client."
                    % (activity.code, activity.name)
                )
