from odoo import fields, models


class CmdbImpactAnalysisWizard(models.TransientModel):
    _name = 'cmdb.impact.analysis.wizard'
    _description = "Résultat d'analyse d'impact CMDB"

    ci_name = fields.Char(string="Élément de configuration", readonly=True)
    result_html = fields.Html(string="Résultat", readonly=True)
