import base64
import csv
import io
from collections import defaultdict
from datetime import datetime, time, timedelta

import pytz

from odoo import _, fields, models
from odoo.exceptions import UserError

from ..models.zk_machine_attendance import DEVICE_TZ


class VillaNovaAttendanceReportWizard(models.TransientModel):
    _name = 'villa.nova.attendance.report.wizard'
    _description = "Rapport de présence : présences, retards et absences"

    date_from = fields.Date(string="Du", required=True,
                             default=lambda self: fields.Date.today().replace(day=1))
    date_to = fields.Date(string="Au", required=True, default=fields.Date.today)
    late_threshold = fields.Float(
        string="Heure limite d'arrivée", default=8.0,
        help="Un pointage d'entrée après cette heure est compté comme un retard.")
    report_type = fields.Selection([
        ('all', "Retards et absences"),
        ('late', "Retards seuls"),
        ('absent', "Absences seules"),
    ], string="Contenu du rapport", default='all', required=True,
        help="Le rapport réunit le détail des retards et celui des absences "
             "dans un seul document.")
    group_by = fields.Selection([
        ('employee', "Par employé"),
        ('date', "Par date"),
    ], string="Regroupement", default='employee', required=True,
        help="Par employé : chaque personne forme un bloc, avec ses dates et son "
             "sous-total — c'est la vue à retenir pour retracer un parcours "
             "individuel. Par date : chaque journée forme un bloc, pour un suivi "
             "quotidien.")
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

    def _working_weekdays(self, employee):
        """Jours de la semaine travailles (0=lundi ... 6=dimanche).

        On retombe sur le calendrier de la societe quand l'employe n'en a pas :
        sans ce repli, un employe sans horaire configure sortait purement et
        simplement du rapport, ses absences comprises - le silence le plus
        trompeur qui soit pour un rapport de presence.
        """
        calendar = employee.resource_calendar_id or employee.company_id.resource_calendar_id
        if not calendar:
            return set()
        return {int(a.dayofweek) for a in calendar.attendance_ids}

    # ------------------------------------------------------------------
    # Jours reellement attendus
    # ------------------------------------------------------------------
    def _expected_working_days(self, employees, days):
        """Pour chaque employe, l'ensemble des dates ou sa presence etait due :
        jours ouvres de son horaire, hors jours feries et hors conges valides.

        Sert a la fois au calcul des absences et a celui de la synthese, pour
        qu'un jour ferie ne puisse pas etre compte absent dans un tableau et
        ouvre dans l'autre.
        """
        self.ensure_one()
        if not employees or not days:
            return {}

        start_utc = self._day_bounds_utc(days[0])[0]
        end_utc = self._day_bounds_utc(days[-1])[1]

        leaves = self.env['hr.leave'].search([
            ('employee_id', 'in', employees.ids),
            ('state', '=', 'validate'),
            ('date_from', '<=', end_utc),
            ('date_to', '>=', start_utc),
        ])
        leave_days_by_employee = defaultdict(set)
        for leave in leaves:
            d = leave.date_from.date()
            while d <= leave.date_to.date():
                leave_days_by_employee[leave.employee_id.id].add(d)
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

        expected = {}
        for employee in employees:
            working_days = self._working_weekdays(employee)
            emp_leaves = leave_days_by_employee.get(employee.id, set())
            expected[employee.id] = {
                day for day in days
                if day.weekday() in working_days
                and day not in holiday_days
                and day not in emp_leaves
            }
        return expected

    def _present_days_by_employee(self, employees, days):
        """Dates effectivement pointees, par employe."""
        self.ensure_one()
        if not employees or not days:
            return {}
        start_utc = self._day_bounds_utc(days[0])[0]
        end_utc = self._day_bounds_utc(days[-1])[1]
        attendances = self.env['hr.attendance'].search([
            ('employee_id', 'in', employees.ids),
            ('check_in', '>=', start_utc),
            ('check_in', '<=', end_utc),
        ])
        present = defaultdict(set)
        for att in attendances:
            local_dt = pytz.utc.localize(att.check_in).astimezone(DEVICE_TZ)
            present[att.employee_id.id].add(local_dt.date())
        return present

    # ------------------------------------------------------------------
    # Calcul des lignes
    # ------------------------------------------------------------------
    def _compute_late_lines(self, employees):
        self.ensure_one()
        days = self._date_range()
        if not employees or not days:
            return []
        start_utc = self._day_bounds_utc(days[0])[0]
        end_utc = self._day_bounds_utc(days[-1])[1]
        attendances = self.env['hr.attendance'].search([
            ('employee_id', 'in', employees.ids),
            ('check_in', '>=', start_utc),
            ('check_in', '<=', end_utc),
        ], order='check_in')

        threshold_minutes = round(self.late_threshold * 60)
        working_days_cache = {}

        # On ne retient que le PREMIER pointage de chaque journee. Sans cela, un
        # employe qui rebadge apres etre sorti (pause, rendez-vous exterieur)
        # declenchait un second retard, calcule sur son heure de retour : un
        # retour a 16h35 produisait "8h35 de retard" et faisait exploser le
        # cumul. On arrive en retard une fois par jour, pas a chaque passage.
        premier_pointage = {}
        for att in attendances:
            employee = att.employee_id
            if employee.id not in working_days_cache:
                working_days_cache[employee.id] = self._working_weekdays(employee)
            local_dt = pytz.utc.localize(att.check_in).astimezone(DEVICE_TZ)
            if local_dt.weekday() not in working_days_cache[employee.id]:
                continue
            cle = (employee.id, local_dt.date())
            if cle not in premier_pointage or local_dt < premier_pointage[cle][1]:
                premier_pointage[cle] = (employee, local_dt)

        lines = []
        for employee, local_dt in premier_pointage.values():
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
        expected = self._expected_working_days(employees, days)
        if not expected:
            return []
        present = self._present_days_by_employee(employees, days)
        lines = []
        for employee in employees:
            emp_present = present.get(employee.id, set())
            for day in sorted(expected.get(employee.id, ())):
                if day not in emp_present:
                    lines.append({'employee': employee, 'date': day})
        return lines

    def _compute_synthesis(self, employees, late_lines, absent_lines):
        """Une ligne par employe : ce que le rapport doit montrer en premier.

        Lister chaque jour de presence individuellement produirait plusieurs
        centaines de lignes sur un mois pour un effectif de quarante personnes -
        un export, pas un rapport. La presence est donc restituee en volume
        (jours pointes) et en qualite (ponctualite), le detail nominatif restant
        reserve aux retards et aux absences, qui appellent une action.
        """
        self.ensure_one()
        days = self._date_range()
        expected = self._expected_working_days(employees, days)

        retards_par_employe = defaultdict(int)
        minutes_par_employe = defaultdict(int)
        for line in late_lines:
            retards_par_employe[line['employee'].id] += 1
            minutes_par_employe[line['employee'].id] += line['delay_minutes']

        absences_par_employe = defaultdict(int)
        for line in absent_lines:
            absences_par_employe[line['employee'].id] += 1

        rows = []
        for employee in employees:
            attendus = len(expected.get(employee.id, ()))
            absences = absences_par_employe.get(employee.id, 0)
            presents = max(attendus - absences, 0)
            retards = retards_par_employe.get(employee.id, 0)
            a_lheure = max(presents - retards, 0)
            rows.append({
                'employee': employee,
                'attendus': attendus,
                'presents': presents,
                'a_lheure': a_lheure,
                'retards': retards,
                'minutes_retard': minutes_par_employe.get(employee.id, 0),
                'absences': absences,
                'ponctualite': (a_lheure * 100.0 / presents) if presents else 0.0,
                'assiduite': (presents * 100.0 / attendus) if attendus else 0.0,
                'sans_horaire': attendus == 0,
            })

        # Les situations a traiter remontent en tete : c'est un rapport d'action,
        # pas un annuaire. A ponctualite egale, le plus absent passe devant.
        rows.sort(key=lambda r: (r['sans_horaire'], r['ponctualite'],
                                 -r['absences'], r['employee'].name or ''))
        return rows

    @staticmethod
    def _totaux(rows):
        """Totaux de la synthese, pour le pied de tableau et les cartes."""
        attendus = sum(r['attendus'] for r in rows)
        presents = sum(r['presents'] for r in rows)
        a_lheure = sum(r['a_lheure'] for r in rows)
        return {
            'effectif': len(rows),
            'attendus': attendus,
            'presents': presents,
            'a_lheure': a_lheure,
            'retards': sum(r['retards'] for r in rows),
            'minutes_retard': sum(r['minutes_retard'] for r in rows),
            'absences': sum(r['absences'] for r in rows),
            'ponctualite': (a_lheure * 100.0 / presents) if presents else 0.0,
            'assiduite': (presents * 100.0 / attendus) if attendus else 0.0,
        }

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
        h, m = divmod(int(minutes), 60)
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

        late_lines = self._compute_late_lines(employees) if self.report_type in ('all', 'late') else []
        absent_lines = self._compute_absent_lines(employees) if self.report_type in ('all', 'absent') else []

        buffer = io.StringIO()
        writer = csv.writer(buffer, delimiter=';')
        writer.writerow([_("Rapport de présence du %(from)s au %(to)s") % {
            'from': self.date_from.strftime('%d/%m/%Y'),
            'to': self.date_to.strftime('%d/%m/%Y'),
        }])
        writer.writerow([])

        if self.report_type == 'all':
            rows = self._compute_synthesis(employees, late_lines, absent_lines)
            writer.writerow([_("SYNTHESE PAR EMPLOYE")])
            writer.writerow([_("Employé"), _("Département"), _("Jours dus"), _("Présents"),
                             _("À l'heure"), _("Retards"), _("Cumul retard (min)"),
                             _("Absences"), _("Ponctualité (%)")])
            for row in rows:
                writer.writerow([
                    row['employee'].name,
                    row['employee'].department_id.name or '',
                    row['attendus'], row['presents'], row['a_lheure'],
                    row['retards'], row['minutes_retard'], row['absences'],
                    '%.1f' % row['ponctualite'],
                ])
            writer.writerow([])

        if self.report_type in ('all', 'late'):
            writer.writerow([_("DETAIL DES RETARDS (arrivée après %s)") % self._format_threshold()])
            writer.writerow([_("Employé"), _("Département"), _("Date"), _("Heure d'arrivée"), _("Retard")])
            for line in sorted(late_lines, key=lambda l: (l['date'], l['employee'].name or '')):
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

        if self.report_type in ('all', 'absent'):
            writer.writerow([_("DETAIL DES ABSENCES (jour dû, non pointé)")])
            writer.writerow([_("Employé"), _("Département"), _("Date")])
            for line in sorted(absent_lines, key=lambda l: (l['date'], l['employee'].name or '')):
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
