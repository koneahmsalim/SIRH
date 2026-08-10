from odoo import api, models


class CalendarEvent(models.Model):
    _inherit = 'calendar.event'

    @api.model_create_multi
    def create(self, vals_list):
        alarm = self.env.ref('calendar.alarm_notif_1', raise_if_not_found=False)  # Notification - 15 minutes
        if alarm:
            for vals in vals_list:
                if vals.get('applicant_id') and not vals.get('alarm_ids'):
                    vals['alarm_ids'] = [(4, alarm.id)]
        return super().create(vals_list)
