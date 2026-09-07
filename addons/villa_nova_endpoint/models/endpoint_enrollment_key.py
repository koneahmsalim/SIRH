import secrets

from werkzeug.security import check_password_hash, generate_password_hash

from odoo import _, api, fields, models
from odoo.exceptions import UserError

PUBLIC_ID_BYTES = 6
SECRET_BYTES = 32


class ItsmEndpointEnrollmentKey(models.Model):
    """Cle d'enrolement organisationnelle/site (deploiement de masse GPO/MSI -
    Objectif 6 du brief RMM) - PAS un secret par poste : plusieurs agents
    peuvent s'enroler avec la meme cle (ex. une cle "Sieges Abidjan" glissee
    dans un installateur pousse par GPO a 50 postes). La securite par poste
    vient d'ailleurs : chaque agent reçoit un secret UNIQUE et propre a la fin
    de l'enrolement (voir itsm.endpoint.agent) - cette cle ne sert qu'a
    l'admission initiale, jamais au check-in quotidien, et est revocable a
    tout moment sans casser les postes deja enroles.

    Format du jeton complet communique a l'admin (jamais stocke en clair,
    montre une seule fois) : "<public_id>.<secret>" - permet un lookup direct
    O(1) sur public_id plutot qu'un scan de toutes les cles en comparant leur
    hash (meme logique que les cles API type Stripe/GitHub)."""
    _name = 'itsm.endpoint.enrollment.key'
    _description = "Clé d'enrôlement d'agents endpoint"
    _inherit = ['mail.thread']
    _order = 'create_date desc'

    name = fields.Char(string="Nom", required=True, tracking=True,
                        help="Ex. \"Déploiement GPO - Sièges Abidjan\".")
    public_id = fields.Char(string="Identifiant public", copy=False, readonly=True, index=True)
    key_hash = fields.Char(string="Hash de la clé", copy=False, readonly=True)
    active = fields.Boolean(string="Active", default=True, tracking=True)
    expiry_date = fields.Datetime(string="Expire le", help="Vide = n'expire jamais.")
    max_uses = fields.Integer(string="Nombre d'utilisations max.", default=0,
                               help="0 = illimité.")
    use_count = fields.Integer(string="Utilisations", compute='_compute_use_count', store=True)

    agent_ids = fields.One2many('itsm.endpoint.agent', 'enrollment_key_id', string="Agents enrôlés")
    agent_count = fields.Integer(string="Nombre d'agents", compute='_compute_use_count', store=True)

    @api.depends('agent_ids')
    def _compute_use_count(self):
        for key in self:
            key.use_count = len(key.agent_ids)
            key.agent_count = len(key.agent_ids)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            if not record.public_id:
                record._generate_key()
        return records

    def _generate_key(self):
        """Genere un nouveau secret, ecrase le hash existant (une cle
        regeneree invalide silencieusement l'ancienne - equivalent a une
        rotation) et renvoie le jeton complet en clair pour affichage unique
        a l'admin. N'est jamais rappelable ensuite : seul le hash persiste."""
        self.ensure_one()
        public_id = secrets.token_hex(PUBLIC_ID_BYTES)
        secret = secrets.token_urlsafe(SECRET_BYTES)
        self.write({
            'public_id': public_id,
            'key_hash': generate_password_hash(secret),
        })
        return "%s.%s" % (public_id, secret)

    def action_generate_key(self):
        """Ouvre l'assistant qui affiche le jeton complet une seule fois -
        jamais consultable a nouveau apres fermeture de cette fenetre."""
        self.ensure_one()
        token = self._generate_key()
        wizard = self.env['itsm.endpoint.enrollment.key.reveal'].create({
            'key_id': self.id,
            'token': token,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _("Jeton d'enrôlement (à copier maintenant)"),
            'res_model': 'itsm.endpoint.enrollment.key.reveal',
            'view_mode': 'form',
            'res_id': wizard.id,
            'target': 'new',
        }

    def action_revoke(self):
        self.write({'active': False})

    @api.model
    def _find_valid(self, token):
        """Retrouve la cle a partir du jeton complet "<public_id>.<secret>" et
        valide activite/expiration/quota. Renvoie la cle ou None (jamais
        d'exception ici : c'est au controleur de traduire ça en 401 sans fuite
        d'info sur la raison precise du refus)."""
        if not token or '.' not in token:
            return None
        public_id, _sep, secret = token.partition('.')
        key = self.sudo().search([('public_id', '=', public_id)], limit=1)
        if not key or not key.active:
            return None
        if not check_password_hash(key.key_hash, secret):
            return None
        if key.expiry_date and key.expiry_date < fields.Datetime.now():
            return None
        if key.max_uses and key.use_count >= key.max_uses:
            return None
        return key

    def unlink(self):
        for key in self:
            if key.agent_ids:
                raise UserError(_(
                    "Impossible de supprimer une clé ayant déjà servi à enrôler des agents "
                    "(%(name)s) - révoquez-la plutôt pour conserver l'audit.", name=key.name))
        return super().unlink()
