from odoo import _, fields, models


class HrJob(models.Model):
    _inherit = 'hr.job'

    x_motif_recrutement = fields.Selection(
        [
            ('creation', "Création de poste"),
            ('remplacement', "Remplacement suite à un départ"),
            ('renforcement', "Renforcement des équipes"),
        ],
        string="Motif du recrutement",
    )
    x_delai_souhaite = fields.Date(string="Délai souhaité pour le recrutement")
    x_currency_id = fields.Many2one(related='company_id.currency_id', string="Devise")
    x_budget_recrutement = fields.Monetary(
        string="Budget de recrutement alloué", currency_field='x_currency_id',
    )
    x_objectifs_3_mois = fields.Text(string="Objectifs à 3 mois")
    x_objectifs_1_an = fields.Text(string="Objectifs à 1 an")
    x_validation_state = fields.Selection(
        [
            ('draft', "Brouillon"),
            ('to_validate', "À valider par la Direction Générale"),
            ('validated', "Validé et publié"),
        ],
        string="Statut de validation",
        default='draft',
        tracking=True,
        copy=False,
    )

    def _get_direction_generale_users(self):
        group = self.env.ref(
            'villa_nova_recruitment.group_direction_generale', raise_if_not_found=False,
        )
        return group.users if group else self.env['res.users']

    def action_submit_for_validation(self):
        self.write({'x_validation_state': 'to_validate'})
        users = self._get_direction_generale_users()
        for job in self:
            if users:
                job.message_subscribe(partner_ids=users.mapped('partner_id').ids)
            job.message_post(
                body=_("Poste soumis à la Direction Générale pour validation avant publication."),
            )
            for user in users:
                job.activity_schedule(
                    'mail.mail_activity_data_todo',
                    summary=_("Valider le poste : %s", job.name),
                    note=_(
                        "Motif : %(motif)s. Merci de valider ce poste pour qu'il soit "
                        "publié automatiquement sur le site carrière.",
                        motif=dict(job._fields['x_motif_recrutement'].selection).get(
                            job.x_motif_recrutement, '-',
                        ),
                    ),
                    user_id=user.id,
                )

    def action_validate_job(self):
        self.write({
            'x_validation_state': 'validated',
            'is_published': True,
            'published_date': fields.Date.context_today(self),
        })
        for job in self:
            job.activity_ids.filtered(
                lambda a: a.summary and a.summary.startswith('Valider le poste'),
            ).action_feedback(feedback=_("Poste validé et publié."))
            job.message_post(body=_("Poste validé par la Direction Générale et publié sur le site carrière."))

    def action_reset_to_draft(self):
        self.write({'x_validation_state': 'draft', 'is_published': False})
