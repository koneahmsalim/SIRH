import pytz

from odoo import api, models

# Codes reellement geres nativement par hr_biometric_attendance pour deduire
# entree/sortie ; tout le reste (notamment 255, code generique envoye par le
# boitier F18) doit etre devine.
NATIVE_PUNCH_CODES = ('0', '1')

# Le boitier est physiquement a Abidjan (UTC+0, jamais d'heure d'ete) : ce
# fuseau est fixe en dur partout ou un horodatage de pointage est interprete,
# plutot que derive de l'utilisateur/tache qui declenche le traitement. Le
# cron et `odoo shell` tournent sous le compte systeme __system__, qui avait
# cause un decalage de 2h le 17/08 en restant sur Europe/Brussels (heure
# d'ete) pendant que les comptes reels etaient deja corriges.
DEVICE_TZ = pytz.timezone('Africa/Abidjan')


class ZkMachineAttendance(models.Model):
    _inherit = 'zk.machine.attendance'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        employees = records.filtered(
            lambda r: r.employee_id and r.punch_type not in NATIVE_PUNCH_CODES
        ).employee_id
        # Une importation groupee (plusieurs pointages du meme jour pour un
        # meme employe) peut repeter le meme employe plusieurs fois dans le
        # recordset : on ne reconstruit qu'une fois chacun.
        for employee in employees.browse(set(employees.ids)):
            employee._villa_nova_rebuild_attendance_from_punches()
        return records
