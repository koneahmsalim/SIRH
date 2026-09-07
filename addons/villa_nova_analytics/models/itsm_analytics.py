from datetime import timedelta

from odoo import api, models, fields

TREND_DAYS = 14
SLA_PERIOD_DAYS = 30
PRIORITY_ORDER = ('critical', 'high', 'medium', 'low')


class ItsmTicketAnalytics(models.Model):
    """Agregation cross-modules (ITSM/ITAM/Change) pour le tableau de bord
    analytique gestionnaire - ajoutee via _inherit sur le modele deja
    utilise pour le tableau de bord agent (Phase 1), meme pattern RPC."""
    _inherit = 'itsm.ticket'

    @api.model
    def get_villa_nova_analytics_dashboard(self):
        Ticket = self.env['itsm.ticket']
        now = fields.Datetime.now()
        period_start = now - timedelta(days=SLA_PERIOD_DAYS)

        resolved_recent = Ticket.search([
            ('resolved_date', '>=', period_start), ('resolved_date', '!=', False),
        ])
        sla_met = resolved_recent.filtered(lambda t: t.sla_resolution_status == 'met')
        sla_compliance = round(100.0 * len(sla_met) / len(resolved_recent), 1) if resolved_recent else None

        trend = []
        for offset in range(TREND_DAYS - 1, -1, -1):
            day_start = (now - timedelta(days=offset)).replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)
            trend.append({
                'label': day_start.strftime('%d/%m'),
                'created': Ticket.search_count([('create_date', '>=', day_start), ('create_date', '<', day_end)]),
                'resolved': Ticket.search_count([('resolved_date', '>=', day_start), ('resolved_date', '<', day_end)]),
            })

        resolution_by_priority = {}
        for priority in PRIORITY_ORDER:
            tickets = resolved_recent.filtered(lambda t, p=priority: t.priority == p)
            if tickets:
                # max(0, ...) : un ticket resolu dans la meme seconde que sa
                # creation peut produire un delta infime negatif (resolved_date
                # est tronque a la seconde en base, create_date garde les
                # microsecondes) - une duree de resolution n'est jamais negative.
                durations = [
                    max(0.0, (t.resolved_date - t.create_date).total_seconds() / 3600.0) for t in tickets
                ]
                resolution_by_priority[priority] = round(sum(durations) / len(durations), 1)
            else:
                resolution_by_priority[priority] = 0.0

        categories = self.env['itsm.category'].search([])
        category_counts = []
        for category in categories:
            count = Ticket.search_count([('create_date', '>=', period_start), ('category_id', '=', category.id)])
            if count:
                category_counts.append({'name': category.name, 'count': count})
        category_counts.sort(key=lambda c: -c['count'])

        csat = {
            'great': Ticket.search_count([('satisfaction_rating', '=', 'great')]),
            'okay': Ticket.search_count([('satisfaction_rating', '=', 'okay')]),
            'bad': Ticket.search_count([('satisfaction_rating', '=', 'bad')]),
        }

        Equipment = self.env['maintenance.equipment']
        equip_with_status = Equipment.search([('compliance_status', '!=', 'unknown')])
        compliant = equip_with_status.filtered(lambda e: e.compliance_status == 'compliant')
        itam_compliance = round(100.0 * len(compliant) / len(equip_with_status), 1) if equip_with_status else None

        License = self.env['itam.software.license']
        over_allocated_licenses = License.search_count([('is_over_allocated', '=', True)])

        Change = self.env['itsm.change']
        finished_changes = Change.search([('state', 'in', ('implemented', 'failed'))])
        successful_changes = finished_changes.filtered(lambda c: c.state == 'implemented')
        change_success_rate = (
            round(100.0 * len(successful_changes) / len(finished_changes), 1) if finished_changes else None
        )

        return {
            'sla_compliance': sla_compliance,
            'trend': trend,
            'resolution_by_priority': resolution_by_priority,
            'top_categories': category_counts[:5],
            'csat': csat,
            'itam_compliance': itam_compliance,
            'over_allocated_licenses': over_allocated_licenses,
            'change_success_rate': change_success_rate,
        }
