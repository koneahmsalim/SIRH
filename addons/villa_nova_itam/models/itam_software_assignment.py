from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ItamSoftwareAssignment(models.Model):
    _name = 'itam.software.assignment'
    _description = "Attribution de licence logicielle"
    _order = 'assign_date desc'

    license_id = fields.Many2one('itam.software.license', string="Licence", required=True, ondelete='cascade')
    employee_id = fields.Many2one('hr.employee', string="Employé")
    equipment_id = fields.Many2one('maintenance.equipment', string="Actif")
    assign_date = fields.Date(string="Attribuée le", default=fields.Date.context_today, required=True)
    unassign_date = fields.Date(string="Révoquée le")
    active = fields.Boolean(default=True)
    notes = fields.Char(string="Notes")

    # @api.constrains seul ne suffit pas ici : Odoo ne le declenche a la
    # creation que si l'un des champs lies figure dans les vals fournis - un
    # create() qui ne fournit ni employee_id ni equipment_id du tout passerait
    # sans etre verifie. La contrainte SQL est la garantie reelle ; le
    # @api.constrains reste pour un message d'erreur clair des que l'un des
    # deux champs est effectivement modifie.
    _sql_constraints = [
        ('target_required', 'CHECK (employee_id IS NOT NULL OR equipment_id IS NOT NULL)',
         "Une attribution doit concerner un employé ou un actif."),
    ]

    @api.constrains('employee_id', 'equipment_id')
    def _check_target(self):
        for assignment in self:
            if not assignment.employee_id and not assignment.equipment_id:
                raise ValidationError(_("Une attribution doit concerner un employé ou un actif."))

    def action_revoke(self):
        for assignment in self:
            assignment.write({'active': False, 'unassign_date': fields.Date.context_today(assignment)})
