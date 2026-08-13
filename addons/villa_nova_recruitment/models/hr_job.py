from odoo import _, api, fields, models
from odoo.exceptions import UserError


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
    x_date_cloture = fields.Date(
        string="Date de clôture des candidatures",
        help="Date limite de réception des candidatures, à mentionner dans l'annonce.",
    )
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

    def write(self, vals):
        if vals.get('is_published'):
            new_state = vals.get('x_validation_state')
            not_validated = self.filtered(
                lambda job: (new_state or job.x_validation_state) != 'validated',
            )
            if not_validated:
                raise UserError(_(
                    "Ce poste ne peut être publié qu'après validation par la Direction "
                    "Générale (bouton « Soumettre pour validation » puis validation DG)."
                ))
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        jobs = super().create(vals_list)
        # Le bouton "Nouveau" de l'app Recrutement redirige immediatement vers le
        # kanban des candidatures du poste, sans jamais montrer l'onglet
        # Planification ni le bouton "Soumettre pour validation". Sans ce rappel,
        # une RH pressee peut tres bien ne jamais revenir completer/valider le
        # poste, qui ne sera alors jamais publie. hr.job n'a pas mail.activity.mixin
        # (uniquement mail.thread) : on utilise une notification directe plutot
        # qu'une tache formelle.
        for job in jobs:
            job.message_notify(
                partner_ids=self.env.user.partner_id.ids,
                subject=_("Poste « %s » créé", job.name),
                body=_(
                    "Ce poste n'est pas encore publié. Complétez l'onglet « Planification du "
                    "recrutement » (délai, budget, objectifs) puis cliquez sur « Soumettre pour "
                    "validation » pour que la Direction Générale puisse le valider."
                ),
            )
        return jobs

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
            motif = dict(job._fields['x_motif_recrutement'].selection).get(
                job.x_motif_recrutement, '-',
            )
            job.message_post(
                body=_(
                    "Poste soumis à la Direction Générale pour validation avant publication. "
                    "Motif : %(motif)s.", motif=motif,
                ),
            )
            if users:
                job.message_notify(
                    partner_ids=users.mapped('partner_id').ids,
                    subject=_("Poste à valider : %s", job.name),
                    body=_(
                        "Motif : %(motif)s. Merci de valider ce poste pour qu'il soit publié "
                        "automatiquement sur le site carrière.", motif=motif,
                    ),
                )

    def action_validate_job(self):
        self.write({
            'x_validation_state': 'validated',
            'is_published': True,
            'published_date': fields.Date.context_today(self),
        })
        for job in self:
            job.message_post(body=_("Poste validé par la Direction Générale et publié sur le site carrière."))

    def action_reset_to_draft(self):
        self.write({'x_validation_state': 'draft', 'is_published': False})
