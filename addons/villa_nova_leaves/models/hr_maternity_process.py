from odoo import _, fields, models


class HrMaternityProcess(models.Model):
    _name = 'hr.maternity.process'
    _description = "Processus de congé maternité Villa Nova"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_annonce desc'

    employee_id = fields.Many2one('hr.employee', string="Collaboratrice", required=True, tracking=True)
    stage = fields.Selection(
        [
            ('a_annonce', "a) Annonce de la grossesse (confidentiel RH)"),
            ('b_consultation', "b) Consultation avec les RH"),
            ('c_documents', "c) Préparation des documents"),
            ('d_demande', "d) Demande officielle de congé maternité"),
            ('e_validation', "e) Validation de la demande"),
            ('f_retour', "f) Retour au travail"),
            ('g_cloture', "g) Clôturé (communication continue terminée)"),
        ],
        default='a_annonce', tracking=True, group_expand='_expand_stages',
    )

    date_annonce = fields.Date(string="Date de l'annonce", default=fields.Date.context_today)
    date_consultation_rh = fields.Date(string="Date de la consultation RH")

    cert_grossesse_3_mois = fields.Boolean(string="Certificat de grossesse - 3ème mois reçu")
    cert_grossesse_6_mois = fields.Boolean(string="Certificat de grossesse - 6ème mois reçu")
    cert_grossesse_7_mois = fields.Boolean(string="Certificat de grossesse - 7ème mois reçu")
    cert_medecin_traitant = fields.Boolean(string="Certificat du médecin traitant reçu")

    leave_id = fields.Many2one('hr.leave', string="Congé maternité (SIRH)")
    date_demande_officielle = fields.Date(string="Date de la demande officielle")

    date_validation = fields.Date(string="Date de validation RH")
    confirmation_ecrite_envoyee = fields.Boolean(string="Confirmation écrite envoyée à la collaboratrice")

    date_retour_prevue = fields.Date(
        string="Date de retour prévisionnelle communiquée",
        help="À communiquer par la collaboratrice au moins un mois avant la fin du congé.",
    )
    attestation_reprise_delivree = fields.Boolean(string="Attestation de reprise délivrée")

    notes_communication_continue = fields.Text(
        string="Suivi de la communication pendant le congé",
        help="Lien humain et professionnel maintenu, informations importantes transmises "
             "(notamment pour les collaboratrices à un poste de Manager), préparation du retour.",
    )

    def _expand_stages(self, stages, domain):
        return [key for key, _label in self._fields['stage'].selection]

    def action_confirm_annonce(self):
        for process in self:
            process.stage = 'b_consultation'
            rh_users = process._get_rh_users()
            for user in rh_users:
                process.activity_schedule(
                    'mail.mail_activity_data_todo',
                    summary=_("Organiser la consultation congé maternité : %s", process.employee_id.name),
                    note=_(
                        "Présenter les droits légaux, expliquer les démarches administratives, "
                        "informer sur les avantages sociaux et la rémunération, planifier les "
                        "étapes jusqu'au retour au travail."
                    ),
                    user_id=user.id,
                )

    def action_confirm_consultation(self):
        self.write({'stage': 'c_documents', 'date_consultation_rh': fields.Date.context_today(self)})

    def action_confirm_documents(self):
        self.write({'stage': 'd_demande'})

    def action_confirm_demande(self):
        self.write({'stage': 'e_validation', 'date_demande_officielle': fields.Date.context_today(self)})

    def action_confirm_validation(self):
        for process in self:
            process.write({
                'stage': 'f_retour',
                'date_validation': fields.Date.context_today(process),
                'confirmation_ecrite_envoyee': True,
            })
            if process.employee_id.user_id:
                process.message_notify(
                    partner_ids=process.employee_id.user_id.partner_id.ids,
                    subject=_("Votre congé maternité est validé"),
                    body=_(
                        "Merci de nous communiquer votre date de retour prévisionnelle au moins "
                        "un mois avant la fin de votre congé."
                    ),
                )

    def action_confirm_retour(self):
        for process in self:
            process.write({'stage': 'g_cloture', 'attestation_reprise_delivree': True})

    def _get_rh_users(self):
        group = self.env.ref('villa_nova_recruitment.group_direction_generale', raise_if_not_found=False)
        return group.users if group else self.env['res.users']
