from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError

TICKET_TYPE_SELECTION = [
    ('incident', "Incident"),
    ('service_request', "Demande de service"),
    ('question', "Question"),
    ('complaint', "Réclamation"),
]

STATE_SELECTION = [
    ('new', "Nouveau"),
    ('assigned', "Assigné"),
    ('in_progress', "En cours"),
    ('pending', "En attente"),
    ('resolved', "Résolu"),
    ('closed', "Clôturé"),
    ('cancelled', "Annulé"),
]

# Etats "ouverts" du point de vue metier (charge de travail active) - la
# distinction resolved/closed est volontaire (comme dans tout ITSM serieux) :
# resolu = le technicien a fini, cloture = le demandeur (ou un delai
# d'auto-cloture, Phase 3) a confirme que ca reste regle.
OPEN_STATES = ('new', 'assigned', 'in_progress', 'pending')

IMPACT_URGENCY_SELECTION = [
    ('low', "Faible"),
    ('medium', "Moyenne"),
    ('high', "Élevée"),
]

PRIORITY_SELECTION = [
    ('low', "Basse"),
    ('medium', "Moyenne"),
    ('high', "Haute"),
    ('critical', "Critique"),
]

SOURCE_SELECTION = [
    ('backend', "Interface Odoo"),
    ('portal', "Portail"),
    ('email', "E-mail"),
    ('phone', "Téléphone"),
]

# Matrice ITIL classique impact x urgence -> priorite. Volontairement un
# simple dict plutot qu'un modele configurable : la matrice de priorisation
# est une decision organisationnelle rare a changer, pas une donnee de
# parametrage quotidien - un modele dedie ajouterait de la complexite pour
# un besoin qui ne s'est pas encore manifeste.
PRIORITY_MATRIX = {
    ('high', 'high'): 'critical',
    ('high', 'medium'): 'high',
    ('medium', 'high'): 'high',
    ('high', 'low'): 'medium',
    ('low', 'high'): 'medium',
    ('medium', 'medium'): 'medium',
    ('medium', 'low'): 'low',
    ('low', 'medium'): 'low',
    ('low', 'low'): 'low',
}

SLA_STATUS_SELECTION = [
    ('on_track', "Dans les temps"),
    ('at_risk', "À risque"),
    ('breached', "Dépassé"),
    ('met', "Respecté"),
]

# Seuil a partir duquel un SLA non encore depasse passe visuellement
# "a risque" - donne a l'agent un signal avant la deadline, pas seulement
# un banc binaire respecte/depasse.
SLA_AT_RISK_RATIO = 0.8


class ItsmTicket(models.Model):
    """Modele central du Service Desk. Unifie incident / demande de service /
    question / reclamation sous un seul modele (ticket_type) plutot que des
    modeles separes : ce sont les memes mecaniques (SLA, conversation,
    workflow, relations) avec juste une etiquette differente - separer
    aurait duplique toute la machinerie pour un gain nul. Le Problem
    Management (Phase 7) sera lui un modele distinct relie par
    problem_id, car son cycle de vie est reellement different (un probleme
    n'a pas de SLA de reponse par exemple).

    Concu pour etre etendu par les phases futures via _inherit plutot que
    par des champs prepares a l'avance : Phase 4 (ITAM) ajoutera
    asset_id, Phase 6 (CMDB) ajoutera ci_ids, Phase 7 ajoutera problem_id/
    change_id/release_id, Phase 11 ajoutera contract_id/vendor_id - aucun
    de ces champs n'existe encore ici pour ne pas polluer le modele avec
    des relations vers des modeles qui n'existent pas."""
    _name = 'itsm.ticket'
    _description = "Ticket ITSM"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _order = 'priority_sequence, create_date desc'
    _rec_name = 'name'

    name = fields.Char(string="Référence", required=True, copy=False, readonly=True, default='Nouveau')
    ticket_type = fields.Selection(TICKET_TYPE_SELECTION, string="Type", required=True, default='incident', tracking=True)
    subject = fields.Char(string="Sujet", required=True, tracking=True)
    description = fields.Html(string="Description")
    source = fields.Selection(SOURCE_SELECTION, string="Source", default='backend', required=True)

    state = fields.Selection(STATE_SELECTION, string="Statut", default='new', required=True, tracking=True,
                              group_expand='_expand_states', index=True)
    active = fields.Boolean(default=True)

    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)

    # index=True sur partner_id : evalue a chaque chargement de liste/page
    # portail (regle "partner_id = moi OU je suis dans les destinataires du
    # message"), state/category_id/service_id : filtres les plus frequents
    # du tableau de bord et de l'agregation analytique (Phase 10).
    partner_id = fields.Many2one('res.partner', string="Demandeur", tracking=True, index=True)
    partner_email = fields.Char(related='partner_id.email', string="E-mail du demandeur", readonly=True)
    employee_id = fields.Many2one('hr.employee', string="Employé concerné", tracking=True)
    user_id = fields.Many2one('res.users', string="Agent assigné", tracking=True, index=True)
    team_id = fields.Many2one('itsm.team', string="Équipe", tracking=True, index=True)

    category_id = fields.Many2one('itsm.category', string="Catégorie", tracking=True, index=True)
    service_id = fields.Many2one('itsm.service', string="Service", index=True)
    tag_ids = fields.Many2many('itsm.tag', string="Étiquettes")

    impact = fields.Selection(IMPACT_URGENCY_SELECTION, string="Impact", default='medium', required=True, tracking=True)
    urgency = fields.Selection(IMPACT_URGENCY_SELECTION, string="Urgence", default='medium', required=True, tracking=True)
    # Pas de required=True malgre le compute qui garantit toujours une
    # valeur : un champ calcule+stocke+obligatoire echoue a l'insertion en
    # base (Odoo insere d'abord la ligne puis calcule/met a jour ensuite -
    # la contrainte NOT NULL casse cet ordre des la creation en lot).
    priority = fields.Selection(
        PRIORITY_SELECTION, string="Priorité", compute='_compute_priority', store=True, readonly=False,
        tracking=True, index=True,
        help="Calculée automatiquement à partir de l'impact et de l'urgence (matrice ITIL), modifiable manuellement.",
    )
    priority_sequence = fields.Integer(compute='_compute_priority_sequence', store=True)
    is_major_incident = fields.Boolean(
        string="Incident majeur", tracking=True,
        help="Signale un incident à fort impact nécessitant une communication et un suivi renforcés.",
    )

    # --- Relations ticket-a-ticket -----------------------------------
    parent_ticket_id = fields.Many2one('itsm.ticket', string="Ticket parent", tracking=True, index=True)
    child_ticket_ids = fields.One2many('itsm.ticket', 'parent_ticket_id', string="Tickets enfants")
    child_ticket_count = fields.Integer(compute='_compute_relation_counts')
    linked_ticket_ids = fields.Many2many(
        'itsm.ticket', 'itsm_ticket_link_rel', 'ticket_id', 'linked_ticket_id',
        string="Tickets liés",
    )
    merged_into_id = fields.Many2one('itsm.ticket', string="Fusionné dans", copy=False, tracking=True)

    # --- SLA -----------------------------------------------------------
    sla_policy_id = fields.Many2one(
        'itsm.sla.policy', string="Politique SLA", compute='_compute_sla_policy',
        store=True, readonly=False, tracking=True,
    )
    sla_first_response_deadline = fields.Datetime(string="Échéance 1ère réponse", compute='_compute_sla_deadlines', store=True)
    sla_resolution_deadline = fields.Datetime(string="Échéance résolution", compute='_compute_sla_deadlines', store=True)
    first_responded_at = fields.Datetime(string="Première réponse le", copy=False)
    sla_response_status = fields.Selection(SLA_STATUS_SELECTION, compute='_compute_sla_status', store=True, string="SLA réponse")
    sla_resolution_status = fields.Selection(SLA_STATUS_SELECTION, compute='_compute_sla_status', store=True, string="SLA résolution")
    # Pause SLA : le temps passe "En attente" (cote client/tiers, pas de la
    # faute de l'agent) ne doit pas consommer le SLA - accumule a la sortie
    # de chaque pause, ajoute aux echeances au lieu de les laisser courir.
    sla_pause_started_at = fields.Datetime(copy=False)
    sla_paused_hours = fields.Float(string="Heures SLA en pause", copy=False, default=0.0)

    resolved_date = fields.Datetime(string="Date de résolution", copy=False)
    closed_date = fields.Datetime(string="Date de clôture", copy=False)
    close_notes = fields.Html(string="Notes de résolution")
    pending_reason = fields.Char(string="Motif de mise en attente")
    cancel_reason = fields.Char(string="Motif d'annulation")

    satisfaction_rating = fields.Selection(
        [('great', "😀 Très satisfait"), ('okay', "😐 Moyen"), ('bad', "☹️ Insatisfait")],
        string="Satisfaction", copy=False,
        help="Renseigné par le demandeur depuis le portail après résolution.",
    )

    time_line_ids = fields.One2many('itsm.ticket.time', 'ticket_id', string="Temps passé")
    total_time_spent = fields.Float(compute='_compute_total_time_spent', string="Temps total (h)")

    # --- Approbation -----------------------------------------------------
    requires_approval = fields.Boolean(
        string="Nécessite une approbation", compute='_compute_requires_approval',
        store=True, readonly=False,
        help="Repris automatiquement du service demandé, modifiable manuellement au cas par cas.",
    )
    approval_ids = fields.One2many('itsm.approval', 'ticket_id', string="Approbations")
    approval_state = fields.Selection(
        [('none', "Non requise"), ('to_request', "À demander"), ('pending', "En attente"),
         ('approved', "Approuvée"), ('refused', "Refusée")],
        string="Statut d'approbation", compute='_compute_approval_state', store=True,
    )

    attachment_count = fields.Integer(string="Nombre de pièces jointes", compute='_compute_attachment_count')

    # Plus haut niveau de la matrice d'escalade de l'equipe deja notifie pour
    # LE dépassement SLA courant - remis a 0 des que le ticket sort de l'etat
    # "depasse" (resolu, ou echeance repoussee) pour qu'un futur depassement
    # reparte du niveau 1, voir _cron_refresh_sla_status.
    escalation_level_reached = fields.Integer(string="Niveau d'escalade atteint", default=0, copy=False)

    kanban_color = fields.Integer(compute='_compute_kanban_color')

    # ------------------------------------------------------------------
    # Compute
    # ------------------------------------------------------------------
    @api.model
    def _expand_states(self, states, domain):
        return [key for key, _label in STATE_SELECTION]

    @api.depends('impact', 'urgency')
    def _compute_priority(self):
        for ticket in self:
            ticket.priority = PRIORITY_MATRIX.get((ticket.impact, ticket.urgency), 'medium')

    @api.depends('priority')
    def _compute_priority_sequence(self):
        order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
        for ticket in self:
            ticket.priority_sequence = order.get(ticket.priority, 4)

    @api.depends('service_id', 'category_id', 'team_id')
    def _compute_sla_policy(self):
        for ticket in self:
            ticket.sla_policy_id = (
                ticket.service_id.default_sla_policy_id
                or ticket.category_id.default_sla_policy_id
                or ticket.team_id.default_sla_policy_id
                or False
            )

    @api.depends('sla_policy_id', 'priority', 'create_date', 'team_id', 'sla_paused_hours')
    def _compute_sla_deadlines(self):
        for ticket in self:
            line = ticket.sla_policy_id._get_line(ticket.priority) if ticket.sla_policy_id else False
            if not line:
                ticket.sla_first_response_deadline = False
                ticket.sla_resolution_deadline = False
                continue
            calendar = ticket.sla_policy_id.calendar_id or ticket.team_id.calendar_id or ticket.company_id.resource_calendar_id
            start = ticket.create_date or fields.Datetime.now()
            response_deadline = ticket._sla_add_hours(calendar, start, line.first_response_hours)
            resolution_deadline = ticket._sla_add_hours(calendar, start, line.resolution_hours)
            # Le temps passe en pause (statut "En attente") est rajoute aux
            # deux echeances : un ticket qui attend une reponse du
            # demandeur ne doit pas "perdre" son SLA pendant ce temps mort.
            if ticket.sla_paused_hours:
                response_deadline = ticket._sla_add_hours(calendar, response_deadline, ticket.sla_paused_hours)
                resolution_deadline = ticket._sla_add_hours(calendar, resolution_deadline, ticket.sla_paused_hours)
            ticket.sla_first_response_deadline = response_deadline
            ticket.sla_resolution_deadline = resolution_deadline

    def _sla_add_hours(self, calendar, start, hours):
        """Ajoute N heures ouvrees a `start` selon le calendrier de travail
        (natif resource.calendar) - une echeance SLA doit courir sur des
        heures reellement travaillees, pas sur des heures d'horloge (un
        SLA de 24h ne doit pas expirer un dimanche matin)."""
        self.ensure_one()
        if not start or not hours:
            return start
        start_dt = fields.Datetime.from_string(start) if isinstance(start, str) else start
        if not calendar:
            return start_dt + timedelta(hours=hours)
        try:
            return calendar.plan_hours(hours, start_dt, compute_leaves=True)
        except Exception:
            return start_dt + timedelta(hours=hours)

    @api.depends('sla_first_response_deadline', 'sla_resolution_deadline', 'first_responded_at',
                 'resolved_date', 'state', 'create_date', 'sla_pause_started_at')
    def _compute_sla_status(self):
        now = fields.Datetime.now()
        for ticket in self:
            # Pendant une pause active, le SLA est fige a l'instant de la
            # mise en attente : pas d'avancement vers "a risque"/"depasse"
            # tant que le ticket reste en attente.
            effective_now = ticket.sla_pause_started_at if (ticket.state == 'pending' and ticket.sla_pause_started_at) else now
            ticket.sla_response_status = ticket._sla_status_for(
                ticket.sla_first_response_deadline, ticket.first_responded_at, effective_now, ticket.create_date)
            ticket.sla_resolution_status = ticket._sla_status_for(
                ticket.sla_resolution_deadline, ticket.resolved_date, effective_now, ticket.create_date)
            # Reinitialise ICI (dans le compute, pas dans le cron qui
            # l'appelle) : un changement qui fait sortir le ticket de l'etat
            # "depasse" (echeance repoussee, politique/priorite changee...)
            # peut deja avoir ete applique - donc deja recalcule - AVANT que
            # le cron ne tourne, auquel cas un diff avant/apres cote cron ne
            # verrait jamais la transition. Colocaliser la remise a zero ici
            # garantit qu'elle est jamais manquee, quelle que soit la cause
            # du changement de statut.
            if ticket.sla_resolution_status != 'breached' and ticket.escalation_level_reached:
                ticket.escalation_level_reached = 0

    @api.model
    def _sla_status_for(self, deadline, done_at, now, create_date):
        """on_track / at_risk (>80% de la fenetre ecoulee) / breached
        (echeance depassee, pas encore fait) / met (fait avant l'echeance)."""
        if not deadline:
            return False
        if done_at:
            return 'met' if done_at <= deadline else 'breached'
        if now >= deadline:
            return 'breached'
        window = (deadline - create_date).total_seconds() if create_date else 0
        if window <= 0:
            return 'on_track'
        elapsed_ratio = (now - create_date).total_seconds() / window
        return 'at_risk' if elapsed_ratio >= SLA_AT_RISK_RATIO else 'on_track'

    def _compute_relation_counts(self):
        for ticket in self:
            ticket.child_ticket_count = len(ticket.child_ticket_ids)

    def _compute_total_time_spent(self):
        for ticket in self:
            ticket.total_time_spent = sum(ticket.time_line_ids.mapped('duration'))

    @api.depends('service_id.requires_approval')
    def _compute_requires_approval(self):
        for ticket in self:
            ticket.requires_approval = ticket.service_id.requires_approval

    @api.depends('approval_ids.state', 'requires_approval')
    def _compute_approval_state(self):
        for ticket in self:
            if not ticket.requires_approval:
                ticket.approval_state = 'none'
                continue
            last = ticket.approval_ids.sorted('request_date', reverse=True)[:1]
            ticket.approval_state = last.state if last else 'to_request'

    def _compute_attachment_count(self):
        for ticket in self:
            ticket.attachment_count = self.env['ir.attachment'].search_count([
                ('res_model', '=', 'itsm.ticket'), ('res_id', '=', ticket.id),
            ])

    @api.depends('priority', 'sla_response_status', 'sla_resolution_status')
    def _compute_kanban_color(self):
        color_by_priority = {'critical': 1, 'high': 3, 'medium': 4, 'low': 10}
        for ticket in self:
            if ticket.sla_resolution_status == 'breached' or ticket.sla_response_status == 'breached':
                ticket.kanban_color = 1
            else:
                ticket.kanban_color = color_by_priority.get(ticket.priority, 4)

    def _compute_access_url(self):
        super()._compute_access_url()
        for ticket in self:
            ticket.access_url = '/my/tickets/%s' % ticket.id

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nouveau') == 'Nouveau':
                sequence_code = 'itsm.ticket.%s' % vals.get('ticket_type', 'incident')
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code(sequence_code)
                    or self.env['ir.sequence'].next_by_code('itsm.ticket.incident')
                    or 'Nouveau'
                )
        tickets = super().create(vals_list)
        tickets._portal_ensure_token()
        for ticket in tickets:
            if ticket.partner_id:
                ticket.message_subscribe(partner_ids=ticket.partner_id.ids)
            if ticket.partner_id.email or ticket.employee_id.work_email:
                ticket._send_mail_safe('villa_nova_itsm.mail_template_ticket_created')
        return tickets

    def write(self, vals):
        if 'state' in vals:
            for ticket in self:
                self._check_state_transition(ticket.state, vals['state'])
        newly_assigned = self.filtered(lambda t: vals.get('user_id') and t.user_id.id != vals['user_id']) if 'user_id' in vals else self.browse()

        # Snapshot avant ecriture : il faut savoir quels tickets ENTRENT ou
        # SORTENT de "En attente" pour gerer la pause SLA - apres
        # super().write(), ticket.state reflete deja la nouvelle valeur.
        entering_pending = leaving_pending = self.browse()
        if vals.get('state') == 'pending':
            entering_pending = self.filtered(lambda t: t.state != 'pending')
        elif 'state' in vals:
            leaving_pending = self.filtered(lambda t: t.state == 'pending')

        res = super().write(vals)

        if vals.get('state') == 'resolved':
            self.filtered(lambda t: not t.resolved_date).write({'resolved_date': fields.Datetime.now()})
        if vals.get('state') == 'closed':
            self.filtered(lambda t: not t.closed_date).write({'closed_date': fields.Datetime.now()})

        if entering_pending:
            entering_pending.write({'sla_pause_started_at': fields.Datetime.now()})
        for ticket in leaving_pending:
            if ticket.sla_pause_started_at:
                paused_hours = (fields.Datetime.now() - ticket.sla_pause_started_at).total_seconds() / 3600.0
                ticket.write({
                    'sla_paused_hours': ticket.sla_paused_hours + max(paused_hours, 0.0),
                    'sla_pause_started_at': False,
                })

        for ticket in newly_assigned:
            if ticket.user_id.email:
                ticket._send_mail_safe('villa_nova_itsm.mail_template_ticket_assigned')
        return res

    def _send_mail_safe(self, template_xmlid):
        """Un probleme de configuration email (souvent rencontre dans ce
        projet - serveur sortant absent/mal configure) ne doit jamais
        bloquer le workflow metier du ticket : on log et on continue."""
        self.ensure_one()
        try:
            template = self.env.ref(template_xmlid, raise_if_not_found=False)
            if template:
                template.send_mail(self.id, force_send=False)
        except Exception:
            import logging
            logging.getLogger(__name__).exception(
                "villa_nova_itsm : echec d'envoi d'email (%s) pour le ticket %s", template_xmlid, self.name)

    _ALLOWED_TRANSITIONS = {
        'new': {'assigned', 'in_progress', 'cancelled', 'resolved'},
        'assigned': {'in_progress', 'pending', 'cancelled', 'resolved', 'new'},
        'in_progress': {'pending', 'resolved', 'cancelled', 'assigned'},
        'pending': {'in_progress', 'resolved', 'cancelled'},
        'resolved': {'closed', 'in_progress'},
        'closed': {'in_progress'},
        'cancelled': {'new'},
    }

    def _check_state_transition(self, old_state, new_state):
        if old_state == new_state:
            return
        allowed = self._ALLOWED_TRANSITIONS.get(old_state, set())
        if new_state not in allowed:
            raise UserError(_(
                "Transition de statut non autorisée : %(old)s → %(new)s.",
                old=dict(STATE_SELECTION).get(old_state), new=dict(STATE_SELECTION).get(new_state),
            ))

    # ------------------------------------------------------------------
    # Actions - workflow
    # ------------------------------------------------------------------
    def action_assign_to_me(self):
        self.write({'user_id': self.env.user.id, 'state': 'assigned' if self.state == 'new' else self.state})
        for ticket in self.filtered(lambda t: t.state == 'new'):
            ticket.state = 'assigned'

    def action_start_progress(self):
        self.write({'state': 'in_progress'})

    def action_set_pending(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _("Mettre en attente"),
            'res_model': 'itsm.ticket.pending.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_ticket_ids': self.ids},
        }

    def action_resolve(self):
        blocked = self.filtered(lambda t: t.requires_approval and t.approval_state != 'approved')
        if blocked:
            raise UserError(_(
                "Ce ticket nécessite une approbation avant de pouvoir être résolu : %s.",
                ', '.join(blocked.mapped('name')),
            ))
        return {
            'type': 'ir.actions.act_window',
            'name': _("Résoudre le ticket"),
            'res_model': 'itsm.ticket.resolve.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_ticket_ids': self.ids},
        }

    def action_request_approval(self):
        self.ensure_one()
        if not self.requires_approval:
            raise UserError(_("Ce ticket ne nécessite pas d'approbation."))
        if self.approval_state == 'pending':
            raise UserError(_("Une demande d'approbation est déjà en attente."))
        approver = self.team_id.leader_id or self.service_id.owner_team_id.leader_id
        if not approver:
            raise UserError(_("Aucun responsable d'équipe à désigner comme approbateur."))
        self.env['itsm.approval'].create({
            'ticket_id': self.id,
            'approver_id': approver.id,
        })
        self.message_post(body=_("Approbation demandée à %(approver)s.", approver=approver.name))
        if approver.email:
            self._send_mail_safe('villa_nova_itsm.mail_template_approval_request')

    def action_close(self):
        self.write({'state': 'closed'})

    def action_reopen(self):
        self.write({'state': 'in_progress'})

    def action_cancel(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _("Annuler le ticket"),
            'res_model': 'itsm.ticket.cancel.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_ticket_ids': self.ids},
        }

    def action_merge(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _("Fusionner le ticket"),
            'res_model': 'itsm.ticket.merge.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_source_ticket_id': self.id},
        }

    def action_mark_first_response(self):
        self.filtered(lambda t: not t.first_responded_at).write({'first_responded_at': fields.Datetime.now()})

    def action_open_attachments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Pièces jointes"),
            'res_model': 'ir.attachment',
            'view_mode': 'list,form',
            'domain': [('res_model', '=', 'itsm.ticket'), ('res_id', '=', self.id)],
        }

    def action_view_children(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Tickets enfants"),
            'res_model': 'itsm.ticket',
            'view_mode': 'list,kanban,form',
            'domain': [('parent_ticket_id', '=', self.id)],
            'context': {'default_parent_ticket_id': self.id},
        }

    # Un message envoye publiquement (pas une note interne) marque
    # automatiquement la premiere reponse SLA - evite un clic manuel
    # supplementaire pour l'agent dans le cas courant.
    def message_post(self, **kwargs):
        message = super().message_post(**kwargs)
        is_internal_note = kwargs.get('subtype_xmlid') == 'mail.mt_note'
        if not is_internal_note and kwargs.get('message_type') != 'notification':
            for ticket in self:
                if not ticket.first_responded_at and ticket.user_id and message.author_id == ticket.user_id.partner_id:
                    ticket.first_responded_at = fields.Datetime.now()
        return message

    @api.model
    def get_villa_nova_itsm_dashboard(self):
        """Chiffres cles pour le tableau de bord agent - une seule methode,
        un seul appel RPC, pour ne pas multiplier les aller-retours reseau
        au chargement du dashboard (meme logique que les autres dashboards
        villa_nova de ce projet)."""
        base_domain = [('state', 'not in', ['closed', 'cancelled'])]
        my_domain = base_domain + [('user_id', '=', self.env.uid)]
        counts = {
            'open': self.search_count(base_domain),
            'critical': self.search_count(base_domain + [('priority', '=', 'critical')]),
            'unassigned': self.search_count(base_domain + [('user_id', '=', False)]),
            'assigned_to_me': self.search_count(my_domain),
            'sla_at_risk': self.search_count(base_domain + [
                '|', ('sla_response_status', '=', 'at_risk'), ('sla_resolution_status', '=', 'at_risk')]),
            'sla_breached': self.search_count(base_domain + [
                '|', ('sla_response_status', '=', 'breached'), ('sla_resolution_status', '=', 'breached')]),
        }
        my_tickets = self.search(my_domain, order='priority_sequence, sla_resolution_deadline', limit=8)
        recent = [{
            'id': t.id,
            'name': t.name,
            'subject': t.subject,
            'priority': t.priority,
            'state': t.state,
            'sla_resolution_status': t.sla_resolution_status,
        } for t in my_tickets]
        return {'counts': counts, 'my_tickets': recent}

    @api.model
    def _cron_refresh_sla_status(self):
        """Les statuts SLA (a_risque/depasse) dependent de 'maintenant', pas
        seulement des donnees du ticket : un ticket peut passer a_risque
        ou depasse sans qu'aucun champ ne change. Recalcule periodiquement
        les tickets ouverts pour garder ces indicateurs a jour meme sans
        interaction utilisateur."""
        tickets = self.search([('state', 'in', list(OPEN_STATES))])
        before = {t.id: (t.sla_response_status, t.sla_resolution_status) for t in tickets}
        tickets._compute_sla_status()
        for ticket in tickets:
            old_response, old_resolution = before[ticket.id]
            newly_at_risk_or_breached = (
                ticket.sla_response_status in ('at_risk', 'breached') and old_response == 'on_track'
                or ticket.sla_resolution_status in ('at_risk', 'breached') and old_resolution == 'on_track'
            )
            if newly_at_risk_or_breached and ticket.user_id.email:
                ticket._send_mail_safe('villa_nova_itsm.mail_template_sla_breach_warning')

            if ticket.sla_resolution_status == 'breached':
                ticket._escalate_on_breach()
        self.env.flush_all()
        self.env.cr.commit()

    def _escalate_on_breach(self):
        """Point d'entree unique appele par le cron pour un ticket dont le
        SLA de resolution est actuellement depasse - matrice a plusieurs
        niveaux si l'equipe en a configure une, sinon repli sur l'ancien
        comportement a un seul niveau (responsable d'equipe)."""
        self.ensure_one()
        if self.team_id.escalation_level_ids:
            self._escalate_by_level()
        else:
            self._escalate_to_team_leader()

    def _escalate_by_level(self):
        """Determine le niveau le plus eleve dont le delai est ecoule et,
        s'il est strictement superieur au dernier niveau deja notifie,
        previent son destinataire - un ticket neglige longtemps saute
        directement au niveau approprie plutot que de notifier en rafale
        tous les niveaux intermediaires deja depasses."""
        self.ensure_one()
        if not self.sla_resolution_deadline:
            return
        hours_since_breach = (fields.Datetime.now() - self.sla_resolution_deadline).total_seconds() / 3600.0
        if hours_since_breach < 0:
            return
        due_levels = self.team_id.escalation_level_ids.filtered(lambda l: l.delay_hours <= hours_since_breach)
        if not due_levels:
            return
        target_level = max(due_levels, key=lambda l: l.level)
        if target_level.level <= self.escalation_level_reached:
            return
        self.write({'escalation_level_reached': target_level.level})
        if target_level.notify_user_id.email:
            self._send_mail_safe('villa_nova_itsm.mail_template_sla_escalation')
        self.activity_schedule(
            'mail.mail_activity_data_todo',
            user_id=target_level.notify_user_id.id,
            summary="Escalade niveau %d : SLA dépassé sur %s" % (target_level.level, self.name),
            note="Le ticket <b>%s</b> (%s) a dépassé son échéance de résolution depuis plus de "
                 "%.0fh (niveau d'escalade %d). Agent assigné : %s." % (
                     self.name, self.subject, target_level.delay_hours, target_level.level,
                     self.user_id.name or "non assigné"),
        )

    def _escalate_to_team_leader(self):
        """Escalade hierarchique : des qu'un ticket depasse son SLA de
        resolution, le responsable de l'equipe est prevenu (email + activite
        a faire) - pas seulement l'agent deja notifie plus tot pour le
        risque. Une seule escalade par ticket (evite de spammer a chaque
        passage du cron tant que le ticket reste ouvert et depasse)."""
        self.ensure_one()
        leader = self.team_id.leader_id
        if not leader or leader == self.user_id:
            return
        already_escalated = self.activity_ids.filtered(
            lambda a: a.user_id == leader and 'SLA dépassé' in (a.summary or ''))
        if already_escalated:
            return
        if leader.email:
            self._send_mail_safe('villa_nova_itsm.mail_template_sla_escalation')
        self.activity_schedule(
            'mail.mail_activity_data_todo',
            user_id=leader.id,
            summary="Escalade : SLA dépassé sur %s" % self.name,
            note="Le ticket <b>%s</b> (%s) a dépassé son échéance de résolution. "
                 "Agent assigné : %s." % (self.name, self.subject, self.user_id.name or "non assigné"),
        )

    def action_automation_notify_critical(self):
        """Appelee par la regle d'automatisation native (base.automation,
        declenchee quand priority passe a 'critical') - une activite plutot
        qu'un email seul : reste visible tant que le responsable n'a pas
        traite/marque comme fait, contrairement a un email qui se perd dans
        la boite de reception."""
        for ticket in self:
            leader = ticket.team_id.leader_id
            if not leader:
                continue
            already_notified = ticket.activity_ids.filtered(
                lambda a: a.user_id == leader and 'Ticket critique' in (a.summary or ''))
            if already_notified:
                continue
            ticket.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=leader.id,
                summary="Ticket critique : %s" % ticket.name,
                note="Le ticket <b>%s</b> (%s) est passé en priorité critique." % (ticket.name, ticket.subject),
            )
