from odoo import api, models

# Codes reellement geres nativement par hr_biometric_attendance pour deduire
# entree/sortie ; tout le reste (notamment 255, code generique envoye par le
# boitier F18) doit etre devine.
NATIVE_PUNCH_CODES = ('0', '1')


class ZkMachineAttendance(models.Model):
    _inherit = 'zk.machine.attendance'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        employees = records.filtered(
            lambda r: r.employee_id and r.punch_type not in NATIVE_PUNCH_CODES
        ).employee_id
        for employee in employees:
            employee._villa_nova_rebuild_attendance_from_punches()
        return records
