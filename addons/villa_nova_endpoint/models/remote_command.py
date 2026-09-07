from odoo import _, api, fields, models
from odoo.exceptions import UserError

COMMAND_TYPE_SELECTION = [
    ('restart', "Redémarrer le poste"),
    ('shutdown', "Éteindre le poste"),
    ('logoff', "Déconnecter la session"),
    ('lock', "Verrouiller la session"),
    ('notify_user', "Notifier l'utilisateur"),
    ('service_status', "Vérifier l'état d'un service"),
    ('service_restart', "Redémarrer un service"),
    ('collect_logs', "Collecter les journaux système"),
    ('refresh_inventory', "Forcer l'actualisation de l'inventaire"),
    ('run_script', "Exécuter un script approuvé"),
]

# Actions perturbatrices pour l'utilisateur ou un service potentiellement en
# production - passent par une approbation d'un second gestionnaire ITAM
# avant transmission a l'agent (contrainte explicite du projet : "validation
# des actions sensibles"). Le reste (verrouillage, notification, lecture
# seule) ne perturbe personne et part directement. run_script est TOUJOURS
# sensible, meme si le script est deja approuve en bibliotheque - executer
# un script reste plus puissant que le reste du catalogue, aucune exception.
SENSITIVE_COMMAND_TYPES = ('restart', 'shutdown', 'logoff', 'service_restart', 'run_script')

# Commandes necessitant un parametre texte (nom de service ou message) -
# valide a la soumission plutot que de decouvrir l'erreur cote agent.
PARAMETER_REQUIRED_TYPES = ('service_status', 'service_restart')

STATE_SELECTION = [
    ('draft', "Brouillon"),
    ('pending_approval', "En attente d'approbation"),
    ('pending', "En attente d'envoi"),
    ('sent', "Envoyée à l'agent"),
    ('running', "En cours d'exécution"),
    ('completed', "Terminée"),
    ('failed', "Échouée"),
    ('cancelled', "Annulée"),
    ('refused', "Refusée"),
]

_ALLOWED_TRANSITIONS = {
    'draft': {'pending_approval', 'pending', 'cancelled'},
    'pending_approval': {'pending', 'refused', 'cancelled'},
    'pending': {'sent', 'cancelled'},
    'sent': {'running', 'failed', 'cancelled'},
    'running': {'completed', 'failed'},
    'completed': set(),
    'failed': set(),
    'cancelled': set(),
    'refused': set(),
}


class ItsmRemoteCommand(models.Model):
    """Catalogue FERME de commandes predefinies executables sur un poste via
    son agent - jamais de code/commande arbitraire (contrainte explicite du
    projet, voir COMMAND_TYPE_SELECTION ci-dessus et le meme catalogue cote
    agent Go dans agent/internal/actions/actions.go). run_script fait
    exception controlee a "predefini" : le CONTENU vient d'itsm.approved.script
    (cure par un admin, jamais une chaine libre), et est FIGE (pinned_script_*)
    au moment de la soumission - editer le script en bibliotheque plus tard
    n'affecte jamais une commande deja soumise.

    Etat pending_approval/approval_id reutilise le moteur d'approbation
    existant (itsm.approval, deja utilise par le CAB des changements -
    villa_nova_change) plutot que d'en construire un nouveau - meme
    philosophie de reutilisation que le reste du projet."""
    _name = 'itsm.remote.command'
    _description = "Commande à distance (agent endpoint)"
    _inherit = ['mail.thread']
    _order = 'create_date desc'

    name = fields.Char(string="Référence", default="Nouveau", copy=False, readonly=True)
    equipment_id = fields.Many2one('maintenance.equipment', string="Actif", required=True, index=True)
    agent_id = fields.Many2one(
        'itsm.endpoint.agent', string="Agent endpoint",
        related='equipment_id.endpoint_agent_id', store=True, readonly=True,
    )

    command_type = fields.Selection(COMMAND_TYPE_SELECTION, string="Commande", required=True, tracking=True)
    parameters = fields.Char(
        string="Paramètre",
        help="Nom du service (service_status/service_restart) ou message à afficher (notify_user). "
             "Ignoré pour les autres types de commande.",
    )
    script_id = fields.Many2one('itsm.approved.script', string="Script à exécuter")
    pinned_script_hash = fields.Char(
        string="Empreinte du script (figée)", copy=False, readonly=True,
        help="Empreinte SHA-256 du script APPROUVÉ au moment de la soumission - une édition "
             "ultérieure du script en bibliothèque n'affecte pas cette commande.",
    )
    pinned_script_content = fields.Text(
        string="Contenu du script (figé)", copy=False, readonly=True,
        help="Copie exacte du contenu exécuté, conservée pour l'audit même si le script "
             "en bibliothèque est modifié ou supprimé ensuite.",
    )
    is_sensitive = fields.Boolean(string="Action sensible", compute='_compute_is_sensitive', store=True)

    requested_by = fields.Many2one('res.users', string="Demandé par", default=lambda self: self.env.user,
                                    required=True, readonly=True)
    request_date = fields.Datetime(string="Demandé le", default=fields.Datetime.now, readonly=True)
    state = fields.Selection(STATE_SELECTION, string="Statut", default='draft', required=True,
                              tracking=True, index=True)

    approval_id = fields.Many2one('itsm.approval', string="Approbation", copy=False, readonly=True)

    sent_date = fields.Datetime(string="Envoyée le", readonly=True)
    started_date = fields.Datetime(string="Démarrée le", readonly=True)
    completed_date = fields.Datetime(string="Terminée le", readonly=True)
    result_output = fields.Text(string="Résultat", readonly=True)
    result_error = fields.Text(string="Erreur", readonly=True)

    @api.depends('command_type')
    def _compute_is_sensitive(self):
        for command in self:
            command.is_sensitive = command.command_type in SENSITIVE_COMMAND_TYPES

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nouveau') == 'Nouveau':
                vals['name'] = self.env['ir.sequence'].next_by_code('itsm.remote.command') or 'Nouveau'
        return super().create(vals_list)

    def _check_state_transition(self, old_state, new_state):
        if old_state == new_state:
            return
        allowed = _ALLOWED_TRANSITIONS.get(old_state, set())
        if new_state not in allowed:
            raise UserError(_(
                "Transition non autorisée : %(old)s → %(new)s.",
                old=dict(STATE_SELECTION).get(old_state), new=dict(STATE_SELECTION).get(new_state)))

    def write(self, vals):
        if 'state' in vals:
            for command in self:
                self._check_state_transition(command.state, vals['state'])
        return super().write(vals)

    def action_submit(self):
        for command in self:
            command._submit_one()

    def _submit_one(self):
        self.ensure_one()
        if not self.agent_id or self.agent_id.state != 'enrolled':
            raise UserError(_(
                "Aucun agent endpoint actif sur %(name)s - impossible de transmettre une commande.",
                name=self.equipment_id.display_name))
        if self.command_type in PARAMETER_REQUIRED_TYPES and not self.parameters:
            raise UserError(_(
                "Cette commande nécessite un paramètre (nom du service)."))
        if self.command_type == 'run_script':
            if not self.script_id:
                raise UserError(_("Sélectionnez un script approuvé à exécuter."))
            if not self.script_id.active:
                raise UserError(_("Ce script a été désactivé - il ne peut plus être exécuté."))
            # Figer le contenu MAINTENANT : si le script est edite entre la
            # soumission et l'approbation/execution, c'est TOUJOURS ce
            # contenu-ci (celui vu et approuve) qui sera envoye a l'agent,
            # jamais une version plus recente non revue.
            self.write({
                'pinned_script_hash': self.script_id.content_hash,
                'pinned_script_content': self.script_id.content,
            })

        if not self.is_sensitive:
            self.write({'state': 'pending'})
            return

        managers = self.env.ref('villa_nova_itam.group_itam_manager').users.filtered(
            lambda u: u.id != self.requested_by.id and u.email)
        if not managers:
            raise UserError(_(
                "Cette action est sensible et nécessite l'approbation d'un AUTRE gestionnaire ITAM, "
                "mais aucun autre gestionnaire actif n'a été trouvé - impossible de garantir la "
                "séparation des responsabilités."))
        approval = self.env['itsm.approval'].create({
            'remote_command_id': self.id,
            'approver_id': managers[0].id,
        })
        self.write({'approval_id': approval.id, 'state': 'pending_approval'})
        self.message_post(body=_(
            "Approbation demandée à %(approver)s avant transmission à l'agent.", approver=managers[0].name))

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    # --- Dispatch/rapport - appelés par les contrôleurs, jamais par un
    #     utilisateur interactif directement. ---

    @api.model
    def _dispatch_for_agent(self, agent):
        """Renvoie les commandes 'pending' pour cet agent au format attendu
        par le protocole de check-in, et les marque 'sent' - appelé UNE FOIS
        par check-in, jamais en dehors d'un appel authentifié de l'agent lui-
        même (voir controllers/agent.py)."""
        commands = self.search([('agent_id', '=', agent.id), ('state', '=', 'pending')])
        if not commands:
            return []
        commands.write({'state': 'sent', 'sent_date': fields.Datetime.now()})
        result = []
        for c in commands:
            entry = {'id': c.id, 'command_type': c.command_type, 'parameters': c.parameters or ''}
            if c.command_type == 'run_script':
                entry['script_content'] = c.pinned_script_content or ''
                entry['script_hash'] = c.pinned_script_hash or ''
            result.append(entry)
        return result

    @api.model
    def _report_result(self, agent, command_id, status, output=None, error=None):
        """Applique le compte-rendu d'une commande - le SEUL champ de
        confiance pour identifier la commande est agent_id (deduit de
        l'authentification agent deja verifiee par le controleur), jamais un
        command_id fourni seul : un agent ne peut jamais rapporter le
        resultat de la commande d'un AUTRE poste."""
        command = self.search([('id', '=', command_id), ('agent_id', '=', agent.id)], limit=1)
        if not command:
            raise UserError(_("Commande introuvable pour cet agent."))
        # _check_state_transition() autorise old_state == new_state (no-op
        # volontaire pour des écritures idempotentes ailleurs, ex.
        # itsm.change) - insuffisant ici : un compte-rendu rejoué (retry
        # réseau de l'agent, ou pire, rejeu malveillant) sur une commande
        # DEJA terminale ecraserait silencieusement result_output/
        # result_error d'origine. Blocage explicite, meme raisonnement que
        # itsm.approval.action_approve ("déjà été traitée").
        if command.state in ('completed', 'failed', 'cancelled', 'refused'):
            raise UserError(_("Cette commande a déjà été traitée (statut : %(state)s).", state=command.state))

        vals = {}
        if status == 'running':
            vals = {'state': 'running', 'started_date': fields.Datetime.now()}
        elif status == 'completed':
            vals = {'state': 'completed', 'completed_date': fields.Datetime.now(), 'result_output': output}
        elif status == 'failed':
            vals = {'state': 'failed', 'completed_date': fields.Datetime.now(),
                     'result_output': output, 'result_error': error}
        else:
            raise UserError(_("Statut de compte-rendu inconnu : %(status)s", status=status))
        command.write(vals)
        return command
