import secrets
import uuid
from datetime import timedelta

from werkzeug.security import check_password_hash, generate_password_hash

from odoo import _, api, fields, models

SECRET_BYTES = 32

PLATFORM_SELECTION = [
    ('windows', "Windows"),
    ('linux', "Linux"),
    ('macos', "macOS"),
]

STATE_SELECTION = [
    ('enrolled', "Enrôlé"),
    ('revoked', "Révoqué"),
]

CHECKIN_STALE_MINUTES = 45
CHECKIN_OFFLINE_MINUTES = 180

# Seuil d'ALERTE (activite pour le gestionnaire), volontairement beaucoup
# plus large que CHECKIN_OFFLINE_MINUTES ci-dessus : un poste eteint pour la
# nuit/le week-end passe "hors ligne" au sens connectivite (badge) sans que
# ce soit anormal - seule une absence prolongee justifie une action humaine.
OFFLINE_ALERT_DAYS = 3


class ItsmEndpointAgent(models.Model):
    """Identite dediee par poste (PAS res.users.apikeys, prevu pour une
    poignee de comptes humains/techniques, pas pour une flotte de centaines
    de postes) - un secret unique par machine, jamais partage, jamais stocke
    en clair (seul le hash persiste, meme mecanisme que la cle d'enrolement).
    Cree automatiquement par le controleur d'enrolement, jamais a la main :
    voir controllers/agent.py et enrollment_key._find_valid()."""
    _name = 'itsm.endpoint.agent'
    _description = "Agent endpoint (identité de poste)"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'enrolled_date desc'
    # Pas de contrainte SQL unique(equipment_id) : un actif accumule un
    # HISTORIQUE d'agents au fil des reimagements (un seul 'enrolled' a la
    # fois, les precedents passent 'revoked' - voir _enroll ci-dessous qui
    # est le SEUL point de creation, donc garantit cette regle cote appli).
    _sql_constraints = [
        ('agent_uuid_uniq', 'unique(agent_uuid)', "Cet identifiant d'agent existe déjà."),
    ]

    equipment_id = fields.Many2one('maintenance.equipment', string="Actif", required=True,
                                    ondelete='cascade', index=True)
    enrollment_key_id = fields.Many2one('itsm.endpoint.enrollment.key', string="Clé d'enrôlement utilisée",
                                         ondelete='set null')

    agent_uuid = fields.Char(string="Identifiant agent", copy=False, readonly=True, index=True)
    secret_hash = fields.Char(string="Hash du secret", copy=False, readonly=True)

    state = fields.Selection(STATE_SELECTION, string="Statut", default='enrolled',
                              required=True, tracking=True, index=True)
    platform = fields.Selection(PLATFORM_SELECTION, string="Plateforme", default='windows')
    agent_version = fields.Char(string="Version de l'agent")

    enrolled_date = fields.Datetime(string="Enrôlé le", default=fields.Datetime.now, readonly=True)
    revoked_date = fields.Datetime(string="Révoqué le", readonly=True)
    last_checkin = fields.Datetime(string="Dernier check-in", tracking=True)
    checkin_count = fields.Integer(string="Nombre de check-in", default=0)
    checkin_status = fields.Selection(
        [('online', "En ligne"), ('stale', "Signal faible"), ('offline', "Hors ligne"),
         ('unknown', "Jamais connecté")],
        string="Connectivité", compute='_compute_checkin_status', store=True,
    )

    @api.depends('last_checkin', 'state')
    def _compute_checkin_status(self):
        now = fields.Datetime.now()
        for agent in self:
            if agent.state == 'revoked':
                agent.checkin_status = 'offline'
            elif not agent.last_checkin:
                agent.checkin_status = 'unknown'
            else:
                delta_min = (now - agent.last_checkin).total_seconds() / 60.0
                if delta_min <= CHECKIN_STALE_MINUTES:
                    agent.checkin_status = 'online'
                elif delta_min <= CHECKIN_OFFLINE_MINUTES:
                    agent.checkin_status = 'stale'
                else:
                    agent.checkin_status = 'offline'

    @api.model
    def _cron_refresh_checkin_status(self):
        """checkin_status depend de 'maintenant', pas seulement de
        last_checkin - meme raison que le cron ITAM endpoint_status et le
        cron SLA de l'ITSM (un agent peut passer hors-ligne sans qu'aucun
        champ ne change)."""
        agents = self.search([('state', '=', 'enrolled')])
        agents._compute_checkin_status()
        self.env.cr.commit()

    @api.model
    def _enroll(self, equipment, enrollment_key, platform=None, agent_version=None):
        """Cree une nouvelle identite de poste. Si l'actif avait deja un
        agent (reimagement/reinstallation legitime - cas frequent en RMM),
        l'ancien est automatiquement revoque plutot que de bloquer le
        redeploiement ou de laisser un credential zombie actif - trace dans
        le chatter de l'actif pour audit."""
        existing = self.sudo().search([('equipment_id', '=', equipment.id), ('state', '=', 'enrolled')])
        if existing:
            existing.write({'state': 'revoked', 'revoked_date': fields.Datetime.now()})
            equipment.message_post(body=_(
                "Agent endpoint %(uuid)s révoqué automatiquement (ré-enrôlement d'un nouvel agent "
                "sur ce même actif).", uuid=existing[0].agent_uuid))

        secret = secrets.token_urlsafe(SECRET_BYTES)
        agent = self.sudo().create({
            'equipment_id': equipment.id,
            'enrollment_key_id': enrollment_key.id if enrollment_key else False,
            'agent_uuid': str(uuid.uuid4()),
            'secret_hash': generate_password_hash(secret),
            'platform': platform or 'windows',
            'agent_version': agent_version,
        })
        equipment.message_post(body=_(
            "Nouvel agent endpoint enrôlé (%(uuid)s) via la clé « %(key)s ».",
            uuid=agent.agent_uuid, key=(enrollment_key.name if enrollment_key else "?")))
        return agent, secret

    @api.model
    def _authenticate(self, agent_uuid, secret):
        """Lookup O(1) par agent_uuid (indexe, unique) puis verification du
        secret par hash - jamais de comparaison en clair ni de scan de la
        table. Renvoie l'agent ou None, sans distinguer "inconnu" de
        "revoque"/"mauvais secret" cote reponse HTTP (evite de renseigner un
        attaquant sur la raison precise de l'echec)."""
        if not agent_uuid or not secret:
            return None
        agent = self.sudo().search([('agent_uuid', '=', agent_uuid), ('state', '=', 'enrolled')], limit=1)
        if not agent or not check_password_hash(agent.secret_hash, secret):
            return None
        return agent

    def _escalate_offline(self, notify_users):
        """Meme mecanisme de deduplication par sous-chaine de resume que les
        rappels de garantie/contrat/licence (villa_nova_contracts) - une
        seule activite tant que le poste reste hors ligne, pas une par
        passage de cron."""
        self.ensure_one()
        equipment_name = self.equipment_id.display_name
        for user in notify_users:
            already_notified = self.activity_ids.filtered(
                lambda a: a.user_id == user and equipment_name in (a.summary or ''))
            if already_notified:
                continue
            self.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=user.id,
                summary=_("Poste hors ligne : %(name)s", name=self.equipment_id.display_name),
                note=_(
                    "L'agent endpoint de <b>%(name)s</b> (%(uuid)s) n'a pas fait de check-in "
                    "depuis le %(date)s - vérifier si le poste est éteint durablement, "
                    "débranché du réseau, ou si l'agent/service a un problème.",
                    name=self.equipment_id.display_name, uuid=self.agent_uuid,
                    date=self.last_checkin or _("jamais"),
                ),
            )

    @api.model
    def _cron_alert_offline_agents(self):
        managers = self.env.ref('villa_nova_itam.group_itam_manager').users.filtered('email')
        if not managers:
            return
        threshold = fields.Datetime.now() - timedelta(days=OFFLINE_ALERT_DAYS)
        agents = self.search([
            ('state', '=', 'enrolled'),
            ('last_checkin', '<', threshold),
        ])
        for agent in agents:
            agent._escalate_offline(managers)
        self.env.cr.commit()

    def action_revoke(self):
        self.write({'state': 'revoked', 'revoked_date': fields.Datetime.now()})
        for agent in self:
            agent.equipment_id.message_post(body=_(
                "Agent endpoint %(uuid)s révoqué manuellement.", uuid=agent.agent_uuid))
