import logging
from datetime import datetime

import pytz

from odoo import models

from .zk_machine_attendance import DEVICE_TZ

_logger = logging.getLogger(__name__)


class BiometricDeviceDetails(models.Model):
    _inherit = 'biometric.device.details'

    def action_villa_nova_sync_recent_attendance(self):
        for device in self:
            device._villa_nova_sync_recent_attendance()

    def _cron_villa_nova_sync_attendance(self):
        self.search([]).action_villa_nova_sync_recent_attendance()

    def _villa_nova_sync_recent_attendance(self):
        """Importe uniquement les pointages posterieurs au dernier deja
        connu, au lieu de reparcourir tout l'historique du boitier (des
        dizaines de milliers d'enregistrements, beaucoup trop lent pour un
        rafraichissement frequent)."""
        self.ensure_one()
        from zk import ZK

        MachineAttendance = self.env['zk.machine.attendance']
        Employee = self.env['hr.employee']

        last = MachineAttendance.search([], order='punching_time desc', limit=1)
        since = last.punching_time if last else datetime(2000, 1, 1)

        zk = ZK(self.device_ip, port=self.port_number or 4370, timeout=15,
                password=int(self.device_password or 0), force_udp=False, ommit_ping=False)
        try:
            conn = zk.connect()
        except Exception:
            _logger.warning("Villa Nova biometrie : connexion au boitier %s impossible", self.device_ip)
            return

        try:
            punches = conn.get_attendance()
        finally:
            conn.disconnect()

        new_punches = [p for p in punches if p.timestamp > since]
        if not new_punches:
            return

        created = 0
        for each in sorted(new_punches, key=lambda p: p.timestamp):
            local_dt = DEVICE_TZ.localize(each.timestamp)
            utc_dt = local_dt.astimezone(pytz.utc).replace(tzinfo=None)

            employee = Employee.search([
                ('device_id_num', '=', each.user_id),
                ('company_id', '=', self.company_id.id or self.env.company.id),
            ], limit=1)
            if not employee:
                continue

            duplicate = MachineAttendance.search([
                ('device_id_num', '=', each.user_id),
                ('punching_time', '=', utc_dt),
                ('company_id', '=', employee.company_id.id),
            ], limit=1)
            if duplicate:
                continue

            MachineAttendance.create({
                'employee_id': employee.id,
                'device_id_num': each.user_id,
                'attendance_type': str(each.status),
                'punch_type': str(each.punch),
                'punching_time': utc_dt,
                'address_id': self.address_id.id,
                'company_id': employee.company_id.id,
            })
            created += 1

        _logger.info(
            "Villa Nova biometrie : %s nouveaux pointages importes depuis le boitier %s",
            created, self.device_ip,
        )
