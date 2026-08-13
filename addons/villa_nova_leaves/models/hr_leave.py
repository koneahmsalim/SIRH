from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# Etape 6 du process de conges payes / conges sans solde : delai de 15 jours
# accorde a la Direction Generale pour delivrer l'Attestation de conge /
# valider le conge sans solde, une fois l'approbation manager+RH obtenue.
DIRECTION_DELAY = timedelta(days=15)

# Table des durees de permission exceptionnelle (Article 25.12 du Code du
# travail ivoirien), en jours ouvrables.
PERMISSION_DURATIONS = {
    'mariage_salarie': 4,
    'mariage_enfant': 2,
    'mariage_frere_soeur': 2,
    'deces_proche_1er_degre': 5,
    'deces_proche_2e_degre': 2,
    'naissance_enfant': 2,
    'bapteme_communion': 1,
    'demenagement': 1,
    'autre_deces': 2,
    'autre_mariage': 1,
}
PERMISSION_ANCIENNETE_MOIS = 6
PERMISSION_PLAFOND_JOURS = 10


class HrLeave(models.Model):
    _inherit = 'hr.leave'

    # Etape 6 : Attestation de conge / validation Direction Generale
    x_dg_attestation_delivree = fields.Boolean(string="Attestation délivrée / DG validé")
    x_dg_attestation_date = fields.Date(string="Date de délivrance")
    x_dg_deadline = fields.Datetime(string="Délai Direction Générale (15j)")

    # Conge maladie
    x_certificat_recu = fields.Boolean(string="Certificat médical reçu")

    # Permission exceptionnelle
    x_motif_permission = fields.Selection(
        [
            ('mariage_salarie', "Mariage du salarié (4j)"),
            ('mariage_enfant', "Mariage d'un enfant (2j)"),
            ('mariage_frere_soeur', "Mariage d'un frère ou d'une sœur (2j)"),
            ('deces_proche_1er_degre', "Décès du conjoint, enfant, père ou mère (5j)"),
            ('deces_proche_2e_degre', "Décès d'un frère, sœur, beau-père ou belle-mère (2j)"),
            ('naissance_enfant', "Naissance d'un enfant (2j)"),
            ('bapteme_communion', "Baptême ou première communion d'un enfant (1j)"),
            ('demenagement', "Déménagement (1j)"),
            ('autre_deces', "Décès - membre de famille non listé (2j, non rémunéré)"),
            ('autre_mariage', "Mariage - membre de famille non listé (1j, non rémunéré)"),
        ],
        string="Motif de la permission",
    )
    x_evenement_hors_lieu_emploi = fields.Boolean(string="Événement hors du lieu d'emploi")
    x_distance_evenement = fields.Selection(
        [('lt_400', "Moins de 400 km"), ('gte_400', "400 km ou plus")],
        string="Distance",
    )
    x_jours_delai_route = fields.Integer(
        string="Jours de délai de route (non rémunérés)", compute='_compute_delai_route', store=True,
    )

    @api.depends('x_evenement_hors_lieu_emploi', 'x_distance_evenement')
    def _compute_delai_route(self):
        for leave in self:
            if not leave.x_evenement_hors_lieu_emploi:
                leave.x_jours_delai_route = 0
            elif leave.x_distance_evenement == 'gte_400':
                leave.x_jours_delai_route = 3
            elif leave.x_distance_evenement == 'lt_400':
                leave.x_jours_delai_route = 2
            else:
                leave.x_jours_delai_route = 0

    @api.onchange('x_motif_permission')
    def _onchange_motif_permission(self):
        if self.x_motif_permission:
            days = PERMISSION_DURATIONS.get(self.x_motif_permission, 0)
            if self.date_from:
                self.date_to = self.date_from + timedelta(days=days - 1) if days else self.date_from

    def _is_permission_exceptionnelle(self):
        self.ensure_one()
        return self.holiday_status_id == self.env.ref(
            'villa_nova_leaves.hr_leave_type_permission_exceptionnelle', raise_if_not_found=False,
        )

    def _is_conge_maladie(self):
        self.ensure_one()
        ref = self.env.ref('hr_holidays.holiday_status_sl', raise_if_not_found=False)
        return bool(ref) and self.holiday_status_id == ref

    def _is_conge_payes_annuel(self):
        self.ensure_one()
        ref = self.env.ref('hr_holidays.holiday_status_cl', raise_if_not_found=False)
        return bool(ref) and self.holiday_status_id == ref

    def _is_conge_sans_solde(self):
        self.ensure_one()
        ref = self.env.ref('hr_holidays.holiday_status_unpaid', raise_if_not_found=False)
        return bool(ref) and self.holiday_status_id == ref

    @api.constrains('x_motif_permission', 'employee_id')
    def _check_permission_eligibilite(self):
        for leave in self:
            if not leave.x_motif_permission or not leave._is_permission_exceptionnelle():
                continue
            joining_date = leave.employee_id.joining_date
            if joining_date:
                months = (fields.Date.today().year - joining_date.year) * 12 + (
                    fields.Date.today().month - joining_date.month
                )
                if months < PERMISSION_ANCIENNETE_MOIS:
                    raise ValidationError(_(
                        "Les permissions exceptionnelles nécessitent au moins 6 mois de présence "
                        "dans l'entreprise (Article 25.12 du Code du travail)."
                    ))

    def action_validate(self, check_state=True):
        res = super().action_validate(check_state)
        for leave in self.filtered(lambda l: l.state == 'validate'):
            leave._villa_nova_after_validate()
        return res

    def _villa_nova_after_validate(self):
        self.ensure_one()
        dg_users = self._get_direction_generale_users()
        if self._is_conge_payes_annuel() or self._is_conge_sans_solde():
            self.x_dg_deadline = fields.Datetime.now() + DIRECTION_DELAY
            summary = (
                _("Délivrer l'Attestation de congé : %s", self.employee_id.name)
                if self._is_conge_payes_annuel()
                else _("Valider le congé sans solde : %s", self.employee_id.name)
            )
            for user in dg_users:
                self.activity_schedule(
                    'mail.mail_activity_data_todo',
                    summary=summary,
                    note=_(
                        "Validation manager + RH obtenue. Délai de 15 jours pour la validation "
                        "finale de la Direction Générale (article Politique de congé)."
                    ),
                    date_deadline=fields.Date.context_today(self) + timedelta(days=15),
                    user_id=user.id,
                )
        if self._is_conge_maladie() and not self.x_certificat_recu:
            for user in dg_users:
                self.activity_schedule(
                    'mail.mail_activity_data_todo',
                    summary=_("Vérifier réception du certificat médical : %s", self.employee_id.name),
                    note=_(
                        "Le certificat médical doit être transmis dans un délai raisonnable "
                        "(idéalement 48h). Cochez « Certificat médical reçu » une fois reçu."
                    ),
                    date_deadline=fields.Date.context_today(self) + timedelta(days=2),
                    user_id=user.id,
                )

    def _get_direction_generale_users(self):
        group = self.env.ref('villa_nova_recruitment.group_direction_generale', raise_if_not_found=False)
        return group.users if group else self.env['res.users']

    def action_villa_nova_mark_attestation_delivered(self):
        for leave in self:
            leave.write({
                'x_dg_attestation_delivree': True,
                'x_dg_attestation_date': fields.Date.context_today(leave),
            })
            leave.activity_ids.filtered(
                lambda a: 'Attestation' in (a.summary or '') or 'sans solde' in (a.summary or ''),
            ).action_feedback(feedback=_("Validé par la Direction Générale."))
