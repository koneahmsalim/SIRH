import pytz

from odoo import models

from .zk_machine_attendance import NATIVE_PUNCH_CODES


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    def _villa_nova_rebuild_attendance_from_punches(self):
        """Regle "premier pointage du jour = entree, dernier = sortie" (validee
        en usage reel) plutot qu'une simple alternance : plus fiable des que la
        fenetre d'import ne capture pas le tout premier pointage de la periode
        (le calcul par alternance demarre alors en decalage de phase)."""
        self.ensure_one()
        Attendance = self.env['hr.attendance']
        MachineAttendance = self.env['zk.machine.attendance']
        tz = pytz.timezone(self.env.user.partner_id.tz or 'GMT')

        punches = MachineAttendance.search([
            ('employee_id', '=', self.id),
            ('punch_type', 'not in', list(NATIVE_PUNCH_CODES)),
        ])
        by_day = {}
        for p in punches:
            day = tz.localize(p.punching_time).date()
            by_day.setdefault(day, []).append(p.punching_time)

        # Ne recalcule que les presences deja issues d'un pointage biometrique
        # (memes horodatages), pour ne jamais toucher une saisie manuelle.
        known_times = {t for times in by_day.values() for t in times}
        Attendance.search([('employee_id', '=', self.id)]).filtered(
            lambda a: a.check_in in known_times or (a.check_out and a.check_out in known_times)
        ).unlink()
        # Le solde d'heures sup. journalier (unique par employe+jour) n'est pas
        # toujours nettoye en cascade par le unlink ci-dessus : on le retire
        # explicitement pour les jours qu'on va recreer, sinon la recreation
        # du jour echoue sur la contrainte d'unicite.
        self.env['hr.attendance.overtime'].sudo().search([
            ('employee_id', '=', self.id), ('date', 'in', list(by_day.keys())),
        ]).unlink()

        # Toutes les presences du jour sont creees en un seul appel : les
        # creer une par une declenche le recalcul natif des heures sup. une
        # fois par appel, ce qui peut generer des doublons en collision sur
        # la contrainte d'unicite employe+jour quand plusieurs jours de la
        # meme reconstruction se suivent dans la meme transaction.
        days_sorted = sorted(by_day.keys())
        vals_list = []
        for idx, day in enumerate(days_sorted):
            day_times = sorted(by_day[day])
            check_in = day_times[0]
            is_last_day = (idx == len(days_sorted) - 1)
            if len(day_times) > 1:
                check_out = day_times[-1]
            elif is_last_day:
                check_out = False
            else:
                check_out = check_in
            # Microseconde a zero : le calcul natif des heures sup. (Odoo
            # core) determine le "debut de journee" via .replace(hour=0,
            # minute=0, second=0) sans reinitialiser la microseconde ; une
            # microseconde residuelle fait alors traiter deux fois le meme
            # jour calendaire (deux tuples distincts), ce qui provoque une
            # violation de la contrainte d'unicite employe+jour.
            vals = {'employee_id': self.id, 'check_in': check_in.replace(microsecond=0)}
            if check_out:
                vals['check_out'] = check_out.replace(microsecond=0)
            vals_list.append(vals)
        if vals_list:
            Attendance.create(vals_list)
