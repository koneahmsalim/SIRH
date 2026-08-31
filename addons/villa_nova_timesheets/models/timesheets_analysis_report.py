from odoo import fields, models

from .timesheet_activity import BILLABILITY_DEFAULT


class TimesheetsAnalysisReport(models.Model):
    """timesheets.analysis.report (hr_timesheet) est une vue SQL, et son
    search view (hr_timesheet_report_search) herite de hr_timesheet_line_search
    - le meme parent que notre extension de recherche sur account.analytic.line.
    Odoo compose les deux dans l'arch final peu importe le modele, donc sans
    ces deux colonnes ici, toute vue Analyse (Par employe/projet/tache) plante
    a l'ouverture avec "Unknown field villa_nova_activity_id"."""
    _inherit = "timesheets.analysis.report"

    villa_nova_activity_id = fields.Many2one(
        'villa.nova.timesheet.activity', string="Code activité", readonly=True)
    villa_nova_billability = fields.Selection(BILLABILITY_DEFAULT, string="Facturabilité", readonly=True)

    def _select(self):
        return super()._select() + """,
                A.villa_nova_activity_id AS villa_nova_activity_id,
                A.villa_nova_billability AS villa_nova_billability
        """
