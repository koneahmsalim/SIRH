import base64
import csv
import io
from datetime import datetime, time, timedelta

import pytz

from odoo import _, fields, models
from odoo.exceptions import UserError

from ..models.zk_machine_attendance import DEVICE_TZ


class VillaNovaAttendanceReportWizard(models.TransientModel):
    _name = 'villa.nova.attendance.report.wizard'
    _description = "Rapport de présence : retards et non-pointés"

    date_from = fields.Date(string="Du", required=True,
                             default=lambda self: fields.Date.today().replace(day=1))
    date_to = fields.Date(string="Au", required=True, default=fields.Date.today)
    late_threshold = fields.Float(
        string="Heure limite d'arrivée", default=8.0,
        help="Un pointage d'entrée après cette heure est compté comme un retard.")
    report_type = fields.Selection([
        ('late', "Retards"),
        ('absent', "Non pointé"),
        ('both', "Les deux"),
    ], string="Contenu du rapport", default='both', required=True)
    department_id = fields.Many2one('hr.department', string="Département")
    employee_ids = fields.Many2many(
        'hr.employee', string="Employés",
        domain="[('device_id_num', '!=', False)]",
        help="Laisser vide pour inclure tous les employés suivis par le boîtier biométrique.")

    # ------------------------------------------------------------------
    # Perimetre et bornes de date
    # ------------------------------------------------------------------
    def _get_employees(self):
        self.ensure_one()
        if self.employee_ids:
            employees = self.employee_ids
            if self.department_id:
                employees = employees.filtered(lambda e: e.department_id == self.department_id)
            return employees
        domain = [('device_id_num', '!=', False)]
        if self.department_id:
            domain.append(('department_id', '=', self.department_id.id))
        return self.env['hr.employee'].search(domain)

    def _date_range(self):
        self.ensure_one()
        if self.date_from > self.date_to:
            raise UserError(_("La date de début doit précéder ou égaler la date de fin."))
        last_day = min(self.date_to, fields.Date.today())
        day = self.date_from
        days = []
        while day <= last_day:
            days.append(day)
            day += timedelta(days=1)
        return days

    def _day_bounds_utc(self, day):
        """Bornes UTC [debut, fin] d'une journee calendaire heure du boitier
        (Africa/Abidjan, UTC+0 fixe - cf. DEVICE_TZ)."""
        start_local = DEVICE_TZ.localize(datetime.combine(day, time.min))
        end_local = DEVICE_TZ.localize(datetime.combine(day, time.max))
        return (start_local.astimezone(pytz.utc).replace(tzinfo=None),
                end_local.astimezone(pytz.utc).replace(tzinfo=None))

    @staticmethod
    def _working_weekdays(employee):
        """Jours de la semaine travailles (0=lundi ... 6=dimanche), d'apres
        le calendrier de ressource de l'employe."""
        return {int(a.dayofweek) for a in employee.resource_calendar_id.attendance_ids}

    # ------------------------------------------------------------------
    # Calcul des lignes
    # ------------------------------------------------------------------
    def _compute_late_lines(self, employees):
        self.ensure_one()
        if not employees or not self._date_range():
            return []
        start_utc, _end = self._day_bounds_utc(self.date_from)
        _start, end_utc = self._day_bounds_utc(min(self.date_to, fields.Date.today()))
        attendances = self.env['hr.attendance'].search([
            ('employee_id', 'in', employees.ids),
            ('check_in', '>=', start_utc),
            ('check_in', '<=', end_utc),
        ], order='check_in')

        threshold_minutes = round(self.late_threshold * 60)
        working_days_cache = {}
        lines = []
        for att in attendances:
            employee = att.employee_id
            if employee.id not in working_days_cache:
                working_days_cache[employee.id] = self._working_weekdays(employee)
            local_dt = pytz.utc.localize(att.check_in).astimezone(DEVICE_TZ)
            if local_dt.weekday() not in working_days_cache[employee.id]:
                continue
            minutes_in = local_dt.hour * 60 + local_dt.minute
            if minutes_in > threshold_minutes:
                lines.append({
                    'employee': employee,
                    'date': local_dt.date(),
                    'check_in_local': local_dt,
                    'delay_minutes': minutes_in - threshold_minutes,
                })
        return lines

    def _compute_absent_lines(self, employees):
        self.ensure_one()
        days = self._date_range()
        if not employees or not days:
            return []

        start_utc, _ = self._day_bounds_utc(days[0])
        _, end_utc = self._day_bounds_utc(days[-1])

        attendances = self.env['hr.attendance'].search([
            ('employee_id', 'in', employees.ids),
            ('check_in', '>=', start_utc),
            ('check_in', '<=', end_utc),
        ])
        present_days = set()
        for att in attendances:
            local_dt = pytz.utc.localize(att.check_in).astimezone(DEVICE_TZ)
            present_days.add((att.employee_id.id, local_dt.date()))

        leaves = self.env['hr.leave'].search([
            ('employee_id', 'in', employees.ids),
            ('state', '=', 'validate'),
            ('date_from', '<=', end_utc),
            ('date_to', '>=', start_utc),
        ])
        leave_days_by_employee = {}
        for leave in leaves:
            emp_days = leave_days_by_employee.setdefault(leave.employee_id.id, set())
            d = leave.date_from.date()
            while d <= leave.date_to.date():
                emp_days.add(d)
                d += timedelta(days=1)

        holidays = self.env['resource.calendar.leaves'].search([
            ('date_from', '<=', end_utc),
            ('date_to', '>=', start_utc),
            ('resource_id', '=', False),
        ])
        holiday_days = set()
        for h in holidays:
            d = h.date_from.date()
            while d <= h.date_to.date():
                holiday_days.add(d)
                d += timedelta(days=1)

        lines = []
        for employee in employees:
            working_days = self._working_weekdays(employee)
            emp_leave_days = leave_days_by_employee.get(employee.id, set())
            for day in days:
                if day.weekday() not in working_days:
                    continue
                if day in holiday_days or day in emp_leave_days:
                    continue
                if (employee.id, day) in present_days:
                    continue
                lines.append({'employee': employee, 'date': day})
        return lines

    # ------------------------------------------------------------------
    # Formatage
    # ------------------------------------------------------------------
    def _format_threshold(self):
        self.ensure_one()
        h = int(self.late_threshold)
        m = round((self.late_threshold - h) * 60)
        return '%02d:%02d' % (h, m)

    @staticmethod
    def _format_delay(minutes):
        h, m = divmod(minutes, 60)
        if h:
            return _("%(h)dh%(m)02d") % {'h': h, 'm': m}
        return _("%(m)d min") % {'m': m}

    # ------------------------------------------------------------------
    # Exports
    # ------------------------------------------------------------------
    def action_export_csv(self):
        self.ensure_one()
        employees = self._get_employees()
        if not employees:
            raise UserError(_("Aucun employé ne correspond aux filtres sélectionnés."))

        late_lines = self._compute_late_lines(employees) if self.report_type in ('late', 'both') else []
        absent_lines = self._compute_absent_lines(employees) if self.report_type in ('absent', 'both') else []

        buffer = io.StringIO()
        writer = csv.writer(buffer, delimiter=';')
        writer.writerow([_("Rapport de présence du %(from)s au %(to)s") % {
            'from': self.date_from.strftime('%d/%m/%Y'),
            'to': self.date_to.strftime('%d/%m/%Y'),
        }])
        writer.writerow([])

        if self.report_type in ('late', 'both'):
            writer.writerow([_("RETARDS (arrivée après %s)") % self._format_threshold()])
            writer.writerow([_("Employé"), _("Département"), _("Date"), _("Heure d'arrivée"), _("Retard")])
            for line in sorted(late_lines, key=lambda l: (l['date'], l['employee'].name)):
                writer.writerow([
                    line['employee'].name,
                    line['employee'].department_id.name or '',
                    line['date'].strftime('%d/%m/%Y'),
                    line['check_in_local'].strftime('%H:%M'),
                    self._format_delay(line['delay_minutes']),
                ])
            if not late_lines:
                writer.writerow([_("Aucun retard sur la période.")])
            writer.writerow([])

        if self.report_type in ('absent', 'both'):
            writer.writerow([_("NON POINTÉ")])
            writer.writerow([_("Employé"), _("Département"), _("Date")])
            for line in sorted(absent_lines, key=lambda l: (l['date'], l['employee'].name)):
                writer.writerow([
                    line['employee'].name,
                    line['employee'].department_id.name or '',
                    line['date'].strftime('%d/%m/%Y'),
                ])
            if not absent_lines:
                writer.writerow([_("Aucune absence sur la période.")])

        # BOM utf-8 : Excel (FR) affiche mal les accents sans lui a l'ouverture directe.
        content = buffer.getvalue().encode('utf-8-sig')
        attachment = self.env['ir.attachment'].create({
            'name': 'rapport_presence_%s_%s.csv' % (self.date_from, self.date_to),
            'type': 'binary',
            'datas': base64.b64encode(content),
            'mimetype': 'text/csv',
        })
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % attachment.id,
            'target': 'self',
        }

    def action_export_pdf(self):
        self.ensure_one()
        employees = self._get_employees()
        if not employees:
            raise UserError(_("Aucun employé ne correspond aux filtres sélectionnés."))
        return self.env.ref(
            'villa_nova_biometric_attendance.action_report_attendance_pdf'
        ).report_action(self)
