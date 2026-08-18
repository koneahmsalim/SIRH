from odoo import models


class ReportVillaNovaAttendance(models.AbstractModel):
    _name = 'report.villa_nova_biometric_attendance.presence_report'
    _description = "Rapport de présence (retards / non pointé) - PDF"

    def _get_report_values(self, docids, data=None):
        wizards = self.env['villa.nova.attendance.report.wizard'].browse(docids)
        wizard = wizards[0]
        employees = wizard._get_employees()
        late_lines = wizard._compute_late_lines(employees) if wizard.report_type in ('late', 'both') else []
        absent_lines = wizard._compute_absent_lines(employees) if wizard.report_type in ('absent', 'both') else []
        return {
            'doc_ids': docids,
            'doc_model': 'villa.nova.attendance.report.wizard',
            'docs': wizards,
            'late_lines': sorted(late_lines, key=lambda l: (l['date'], l['employee'].name)),
            'absent_lines': sorted(absent_lines, key=lambda l: (l['date'], l['employee'].name)),
            'threshold_label': wizard._format_threshold(),
            'format_delay': wizard._format_delay,
        }
