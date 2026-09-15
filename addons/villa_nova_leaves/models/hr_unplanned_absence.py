from datetime import timedelta

from odoo import _, api, fields, models

# Les deux delais ne sont plus figes dans le code : ils sont parametrables par
# la RH (Reglages > Conges), avec pour valeurs de depart celles du droit
# ivoirien - decret n98-198 du 7 mars 1998 pour le justificatif, art. 80 du
# Code du travail pour le seuil d'abandon de poste. Une entreprise peut
# accorder un delai plus large que le minimum legal, jamais l'inverse.


class HrUnplannedAbsence(models.Model):
    _name = 'hr.unplanned.absence'
    _description = "Déclaration d'absence non planifiée"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_declaration desc'

    employee_id = fields.Many2one('hr.employee', string="Collaborateur", required=True, tracking=True)
    date_debut = fields.Date(string="Date de début de l'absence", required=True, default=fields.Date.context_today)
    date_declaration = fields.Datetime(
        string="Date de déclaration", default=fields.Datetime.now, required=True,
        help="Doit intervenir dans un délai maximum de 48h à compter du début de l'absence.",
    )
    motif = fields.Text(string="Motif")
    justificatif_recu = fields.Boolean(string="Justificatif reçu")
    justificatif_deadline = fields.Datetime(string="Échéance du justificatif", compute='_compute_deadlines', store=True)
    abandon_poste_deadline = fields.Datetime(string="Seuil d'alerte abandon de poste", compute='_compute_deadlines', store=True)
    state = fields.Selection(
        [
            ('declaree', "Déclarée"),
            ('justifiee', "Justifiée"),
            ('alerte_abandon_poste', "Alerte abandon de poste"),
            ('cloturee', "Clôturée"),
        ],
        default='declaree', tracking=True,
    )

    @api.depends('date_declaration')
    def _compute_deadlines(self):
        delais = self.env['villa.nova.delais.absence']
        justificatif = timedelta(hours=delais.delai_justificatif_heures())
        abandon = timedelta(hours=delais.delai_abandon_poste_heures())
        for absence in self:
            base = absence.date_declaration or fields.Datetime.now()
            absence.justificatif_deadline = base + justificatif
            absence.abandon_poste_deadline = base + abandon

    @api.model_create_multi
    def create(self, vals_list):
        absences = super().create(vals_list)
        for absence in absences:
            rh_users = absence._get_rh_users()
            managers = absence.employee_id.parent_id.user_id
            for user in (rh_users | managers):
                absence.activity_schedule(
                    'mail.mail_activity_data_todo',
                    summary=_(
                        "Vérifier le justificatif d'absence de %(nom)s (délai %(heures)sh)",
                        nom=absence.employee_id.name,
                        heures=self.env['villa.nova.delais.absence'].delai_justificatif_heures(),
                    ),
                    date_deadline=absence.justificatif_deadline.date(),
                    user_id=user.id,
                )
        return absences

    def action_mark_justifiee(self):
        for absence in self:
            absence.write({'justificatif_recu': True, 'state': 'justifiee'})
            absence.activity_ids.unlink()

    def action_close(self):
        self.write({'state': 'cloturee'})

    def _get_rh_users(self):
        group = self.env.ref('villa_nova_recruitment.group_direction_generale', raise_if_not_found=False)
        return group.users if group else self.env['res.users']

    @api.model
    def _cron_check_abandon_poste(self):
        """Article 80 du Code du travail : absence non justifiee au-dela du
        seuil configure (72h par defaut) ->
        alerte abandon de poste (l'employeur PEUT considerer cela comme tel,
        ce n'est jamais automatique : on notifie, on ne prend aucune decision
        a la place de l'entreprise)."""
        overdue = self.search([
            ('state', '=', 'declaree'),
            ('justificatif_recu', '=', False),
            ('abandon_poste_deadline', '<=', fields.Datetime.now()),
        ])
        for absence in overdue:
            absence.state = 'alerte_abandon_poste'
            for user in absence._get_rh_users():
                absence.activity_schedule(
                    'mail.mail_activity_data_warning',
                    summary=_(
                        "⚠ Absence non justifiée depuis %(heures)sh : %(nom)s",
                        heures=self.env['villa.nova.delais.absence'].delai_abandon_poste_heures(),
                        nom=absence.employee_id.name,
                    ),
                    note=_(
                        "Conformément à l'article 80 du Code du travail, l'absence non justifiée "
                        "peut être considérée comme un abandon de poste. Décision à prendre par "
                        "la Direction Générale / RH."
                    ),
                    date_deadline=fields.Date.context_today(absence),
                    user_id=user.id,
                )
