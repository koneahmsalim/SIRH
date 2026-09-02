import pytz
from datetime import time

from odoo import api, fields, models

from .zk_machine_attendance import DEVICE_TZ

# Meme heure d'arrivee attendue que le rapport retards/absences existant
# (villa.nova.attendance.report.wizard.late_threshold, defaut 8h) - avec la
# tolerance de 30 min confirmee par l'utilisateur (arrivee jusqu'a 8h30
# comptee "a l'heure"). Contrairement au rapport, ce seuil n'est pas
# reglable par ecran ici : il sert a un badge visuel + un filtre rapide au
# quotidien, pas a un calcul RH exportable dont les parametres doivent
# rester ajustables au moment de le lancer.
LATE_ARRIVAL_CUTOFF = time(8, 30)


class HrAttendance(models.Model):
    """Ajoute une valeur "Boitier biometrique" a in_mode/out_mode (natifs
    hr_attendance : kiosk/systray/manual/technical) - sans elle, les pointages
    du boitier tombaient par defaut sur "manual", indiscernables d'une vraie
    saisie manuelle RH dans les filtres/rapports natifs."""
    _inherit = 'hr.attendance'

    in_mode = fields.Selection(
        selection_add=[('badge', "Boîtier biométrique")],
        ondelete={'badge': 'set default'},
    )
    out_mode = fields.Selection(
        selection_add=[('badge', "Boîtier biométrique")],
        ondelete={'badge': 'set default'},
    )

    villa_nova_punctuality = fields.Selection(
        [('on_time', "À l'heure"), ('late', "En retard")],
        string="Ponctualité", compute='_compute_villa_nova_punctuality', store=True,
    )

    @api.depends('check_in')
    def _compute_villa_nova_punctuality(self):
        for att in self:
            if not att.check_in:
                att.villa_nova_punctuality = False
                continue
            local_dt = pytz.utc.localize(att.check_in).astimezone(DEVICE_TZ)
            att.villa_nova_punctuality = 'late' if local_dt.time() > LATE_ARRIVAL_CUTOFF else 'on_time'
