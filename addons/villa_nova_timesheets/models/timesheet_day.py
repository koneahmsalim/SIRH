from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class VillaNovaTimesheetDay(models.Model):
    _name = 'villa.nova.timesheet.day'
    _description = "Clôture quotidienne de feuille de temps"
    _order = 'date desc, employee_id'
    _rec_name = 'display_name'

    employee_id = fields.Many2one('hr.employee', string="Collaborateur", required=True,
                                  index=True, ondelete='cascade')
    date = fields.Date(string="Journée", required=True, index=True)
    state = fields.Selection(
        [('en_cours', "En cours de saisie"), ('complete', "Journée terminée")],
        string="État", default='en_cours', required=True,
    )
    completed_at = fields.Datetime(string="Terminée le", readonly=True)
    total_hours = fields.Float(string="Heures saisies", compute='_compute_total_hours')
    display_name = fields.Char(compute='_compute_display_name')

    _sql_constraints = [
        ('employee_date_unique', 'unique(employee_id, date)',
         "Cette journée est déjà enregistrée pour ce collaborateur."),
    ]

    @api.depends('employee_id', 'date')
    def _compute_display_name(self):
        for jour in self:
            jour.display_name = "%s — %s" % (jour.employee_id.name or '?', jour.date or '?')

    @api.depends('employee_id', 'date')
    def _compute_total_hours(self):
        # Les heures ne sont pas stockees : elles doivent refleter les lignes
        # telles qu'elles sont a l'instant de la lecture, y compris si le
        # collaborateur corrige sa saisie apres avoir cloture sa journee.
        for jour in self:
            lignes = self.env['account.analytic.line'].search([
                ('employee_id', '=', jour.employee_id.id),
                ('date', '=', jour.date),
            ])
            jour.total_hours = sum(lignes.mapped('unit_amount'))

    def _destinataires_notification(self):
        """Responsable hierarchique, ou approbateurs des feuilles de temps.

        Le repli n'est pas cosmetique : la quasi-totalite des fiches employe
        n'a aujourd'hui aucun responsable renseigne. Sans lui, la notification
        ne partirait nulle part et la fonctionnalite paraitrait inerte.
        """
        self.ensure_one()
        manager = self.employee_id.parent_id.user_id
        if manager:
            return manager.partner_id
        groupe = self.env.ref('hr_timesheet.group_hr_timesheet_approver', raise_if_not_found=False)
        return groupe.users.partner_id if groupe else self.env['res.partner']

    def action_terminer_journee(self):
        for jour in self:
            if jour.state == 'complete':
                continue
            if not jour.total_hours:
                raise UserError(_(
                    "Aucune heure n'est saisie pour le %s : renseignez votre activité "
                    "avant de clôturer la journée.", jour.date,
                ))
            jour.write({'state': 'complete', 'completed_at': fields.Datetime.now()})

            destinataires = jour._destinataires_notification()
            if not destinataires:
                continue
            self.env['mail.thread'].sudo().message_notify(
                partner_ids=destinataires.ids,
                subject=_("%(nom)s a terminé sa saisie du %(date)s",
                          nom=jour.employee_id.name, date=jour.date),
                body=Markup(
                    "<p><b>%s</b> a déclaré sa journée du <b>%s</b> terminée.</p>"
                    "<p>Total saisi : <b>%s h</b>.</p>"
                ) % (jour.employee_id.name, jour.date, round(jour.total_hours, 2)),
            )

    def action_rouvrir_journee(self):
        """Une journee cloturee par erreur doit pouvoir etre reprise : la
        cloture est une declaration du collaborateur, pas un verrou comptable."""
        self.write({'state': 'en_cours', 'completed_at': False})

    # ------------------------------------------------------------------
    # Interface "Ma semaine"
    # ------------------------------------------------------------------
    @api.model
    def get_week_status(self, employee_id, date_start, date_end):
        """Etat de cloture de chaque journee de la semaine affichee."""
        jours = self.search([
            ('employee_id', '=', employee_id),
            ('date', '>=', date_start), ('date', '<=', date_end),
        ])
        return {jour.date.isoformat(): jour.state for jour in jours}

    @api.model
    def toggle_day(self, employee_id, date):
        """Cloture la journee, ou la rouvre si elle l'etait deja."""
        jour = self.search([('employee_id', '=', employee_id), ('date', '=', date)], limit=1)
        if not jour:
            jour = self.create({'employee_id': employee_id, 'date': date})
        if jour.state == 'complete':
            jour.action_rouvrir_journee()
        else:
            jour.action_terminer_journee()
        return jour.state
