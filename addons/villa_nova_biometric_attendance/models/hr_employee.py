from datetime import datetime, time, timedelta

import pytz

from odoo import fields, models

from .zk_machine_attendance import DEVICE_TZ, NATIVE_PUNCH_CODES

# Ne retraite que les derniers jours a chaque nouveau pointage. Sans cette
# limite, le cout de la reconstruction (recherche + suppression + recreation)
# grandirait indefiniment avec l'anciennete de l'employe, pour des jours qui
# ne bougent plus de toute facon.
REBUILD_WINDOW_DAYS = 5

# Un meme geste physique produit parfois 2 pointages a quelques secondes
# d'intervalle (double lecture d'empreinte sur le boitier) - observe en
# usage reel : entree a 09:06:03 suivie d'un second pointage a 09:06:04,
# interprete a tort comme une sortie immediate par la regle "dernier
# pointage du jour = sortie" tant que ces quasi-doublons ne sont pas
# fusionnes en un seul evenement.
DUPLICATE_PUNCH_WINDOW = timedelta(minutes=2)


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

        # Fenetre alignee sur un debut de journee calendaire (minuit heure du
        # boitier), jamais sur "maintenant moins N jours" : un horodatage
        # exact coupe le jour le plus ancien de la fenetre en deux (les
        # pointages du matin tombent avant l'heure de coupure et sont
        # ignores), ce qui a deja produit une reconstruction erronee - entree
        # recalculee sur un pointage de l'apres-midi, en collision avec
        # l'ancien enregistrement correct reste hors fenetre et donc jamais
        # supprime (erreur native "l'employe a deja effectue un pointage a
        # l'entree").
        window_start_date = DEVICE_TZ.localize(fields.Datetime.now()).date() - timedelta(days=REBUILD_WINDOW_DAYS)
        window_start = DEVICE_TZ.localize(
            datetime.combine(window_start_date, time.min)
        ).astimezone(pytz.utc).replace(tzinfo=None)
        punches = MachineAttendance.search([
            ('employee_id', '=', self.id),
            ('punch_type', 'not in', list(NATIVE_PUNCH_CODES)),
            ('punching_time', '>=', window_start),
        ])
        by_day = {}
        for p in punches:
            day = DEVICE_TZ.localize(p.punching_time).date()
            by_day.setdefault(day, []).append(p.punching_time)

        for day, times in by_day.items():
            times.sort()
            deduped = [times[0]]
            for t in times[1:]:
                if t - deduped[-1] > DUPLICATE_PUNCH_WINDOW:
                    deduped.append(t)
            by_day[day] = deduped

        # Ne recalcule que les presences deja issues d'un pointage biometrique
        # (memes horodatages), pour ne jamais toucher une saisie manuelle.
        known_times = {t for times in by_day.values() for t in times}
        Attendance.search([
            ('employee_id', '=', self.id),
            ('check_in', '>=', window_start),
        ]).filtered(
            lambda a: a.check_in in known_times or (a.check_out and a.check_out in known_times)
        ).unlink()
        # Le solde d'heures sup. journalier (unique par employe+jour) n'est pas
        # toujours nettoye en cascade par le unlink ci-dessus : on le retire
        # explicitement pour les jours qu'on va recreer, sinon la recreation
        # du jour echoue sur la contrainte d'unicite.
        self.env['hr.attendance.overtime'].sudo().search([
            ('employee_id', '=', self.id), ('date', 'in', list(by_day.keys())),
        ]).unlink()

        # Une presence "ouverte" (sans sortie) plus ancienne que la fenetre
        # de reconstruction bloque tout recalcul futur pour cet employe : la
        # contrainte native d'Odoo refuse de creer une nouvelle presence
        # tant qu'une autre reste ouverte, quelle que soit son anciennete -
        # y compris quand la nouvelle presence est un jour bien plus recent.
        # Le pointage de sortie correspondant, s'il existe, est hors de la
        # fenetre qu'on vient d'interroger : impossible de le retrouver. On
        # cloture donc cette presence orpheline a la fin de sa propre
        # journee (hypothese : pointage de sortie jamais remonte par le
        # boitier) plutot que de bloquer indefiniment tous les recalculs
        # suivants pour cet employe des qu'il repointe.
        stale_open = Attendance.search([
            ('employee_id', '=', self.id),
            ('check_out', '=', False),
            ('check_in', '<', window_start),
        ])
        for att in stale_open:
            day_end = DEVICE_TZ.localize(
                datetime.combine(DEVICE_TZ.localize(att.check_in).date(), time.max)
            ).astimezone(pytz.utc).replace(tzinfo=None, microsecond=0)
            att.write({'check_out': day_end, 'out_mode': 'auto_check_out'})

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
            vals = {
                'employee_id': self.id,
                'check_in': check_in.replace(microsecond=0),
                'in_mode': 'badge',
            }
            if check_out:
                vals['check_out'] = check_out.replace(microsecond=0)
                vals['out_mode'] = 'badge'
            vals_list.append(vals)
        if vals_list:
            Attendance.create(vals_list)
