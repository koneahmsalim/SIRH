from datetime import timedelta

from odoo import _, api, fields, models

# Delai avant la fin de periode d'essai pour rappeler au manager de faire le bilan
# ("Taux de validation des periodes d'essai" - indicateur Suivi & Evaluation).
TRIAL_REMINDER_DELAY = timedelta(days=7)


class HrContract(models.Model):
    _inherit = 'hr.contract'

    x_trial_validation_status = fields.Selection(
        [
            ('pending', "En cours"),
            ('validated', "Validée"),
            ('not_validated', "Non validée"),
        ],
        string="Validation de la période d'essai",
        default='pending',
        tracking=True,
        copy=False,
        help="Indicateur de suivi (Procédure d'intégration, IV - Suivi & Évaluation : "
             "« Taux de validation des périodes d'essai »).",
    )
    x_trial_reminder_scheduled = fields.Boolean(copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        contracts = super().create(vals_list)
        contracts._schedule_trial_validation_reminder()
        return contracts

    def write(self, vals):
        res = super().write(vals)
        if 'trial_date_end' in vals:
            self._schedule_trial_validation_reminder()
        return res

    def _schedule_trial_validation_reminder(self):
        for contract in self:
            if not contract.trial_date_end or contract.x_trial_reminder_scheduled:
                continue
            manager = contract.employee_id.parent_id
            if not manager or not manager.user_id:
                continue
            contract.x_trial_reminder_scheduled = True
            contract.activity_schedule(
                'mail.mail_activity_data_todo',
                summary=_("Bilan de fin de période d'essai : %s", contract.employee_id.name),
                note=_(
                    "Évaluation des résultats et décision de validation (ou non) de la période "
                    "d'essai. Merci de mettre à jour le champ « Validation de la période d'essai »."
                ),
                date_deadline=contract.trial_date_end - TRIAL_REMINDER_DELAY,
                user_id=manager.user_id.id,
            )
