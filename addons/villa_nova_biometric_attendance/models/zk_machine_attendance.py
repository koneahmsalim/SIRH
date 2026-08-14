from odoo import api, models

# Codes reellement geres nativement par hr_biometric_attendance pour deduire
# entree/sortie ; tout le reste (notamment 255, code generique envoye par le
# boitier F18) doit etre devine par alternance.
NATIVE_PUNCH_CODES = ('0', '1')


class ZkMachineAttendance(models.Model):
    _inherit = 'zk.machine.attendance'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records.sorted('punching_time'):
            if record.punch_type in NATIVE_PUNCH_CODES or not record.employee_id:
                continue
            record._villa_nova_infer_check_in_out()
        return records

    def _villa_nova_infer_check_in_out(self):
        """Le pointeur ne precise pas s'il s'agit d'une entree ou d'une sortie
        (punch_type hors 0/1) : on deduit par alternance - si le collaborateur
        n'a pas de presence ouverte, ce pointage est une entree ; sinon, c'est
        la sortie de la presence ouverte la plus recente."""
        self.ensure_one()
        Attendance = self.env['hr.attendance']
        open_attendance = Attendance.search([
            ('employee_id', '=', self.employee_id.id),
            ('check_out', '=', False),
        ], order='check_in desc', limit=1)
        if open_attendance and open_attendance.check_in <= self.punching_time:
            open_attendance.write({'check_out': self.punching_time})
        else:
            Attendance.create({
                'employee_id': self.employee_id.id,
                'check_in': self.punching_time,
            })
