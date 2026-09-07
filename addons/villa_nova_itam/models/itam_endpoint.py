from odoo import api, fields, models

ENDPOINT_STALE_HOURS = 24
ENDPOINT_OFFLINE_HOURS = 72

ENDPOINT_STATUS_SELECTION = [
    ('online', "En ligne"),
    ('stale', "Signal faible"),
    ('offline', "Hors ligne"),
    ('unknown', "Inconnu"),
]

AV_STATUS_SELECTION = [
    ('protected', "Protégé"),
    ('at_risk', "À risque"),
    ('unknown', "Inconnu"),
]

PATCH_STATUS_SELECTION = [
    ('up_to_date', "À jour"),
    ('pending', "Mise à jour en attente"),
    ('overdue', "En retard"),
    ('unknown', "Inconnu"),
]

COMPLIANCE_STATUS_SELECTION = [
    ('compliant', "Conforme"),
    ('non_compliant', "Non conforme"),
    ('unknown', "Inconnu"),
]


class MaintenanceEquipment(models.Model):
    """Phase 5 (ESAM + Endpoint Management) : champs alimentables soit
    manuellement, soit par un agent externe reel via le point d'entree de
    decouverte (voir controllers/discovery.py + itam_discovery.py) -
    authentification par cle API native (res.users.apikeys), pas de
    scanner reseau simule."""
    _inherit = 'maintenance.equipment'

    hostname = fields.Char(string="Nom d'hôte")
    ip_address = fields.Char(string="Adresse IP")
    os_name = fields.Char(string="Système d'exploitation")
    os_version = fields.Char(string="Version OS")
    last_seen = fields.Datetime(string="Dernier signalement", tracking=True)
    endpoint_status = fields.Selection(
        ENDPOINT_STATUS_SELECTION, string="Statut endpoint",
        compute='_compute_endpoint_status', store=True,
    )

    av_status = fields.Selection(
        AV_STATUS_SELECTION, string="Antivirus / EDR", default='unknown', tracking=True,
    )
    patch_status = fields.Selection(
        PATCH_STATUS_SELECTION, string="Mises à jour", default='unknown', tracking=True,
    )
    encryption_enabled = fields.Boolean(string="Disque chiffré")
    last_security_scan = fields.Datetime(string="Dernier scan sécurité")
    compliance_status = fields.Selection(
        COMPLIANCE_STATUS_SELECTION, string="Conformité sécurité",
        compute='_compute_compliance_status', store=True, index=True,
    )

    @api.depends('last_seen')
    def _compute_endpoint_status(self):
        now = fields.Datetime.now()
        for equipment in self:
            if not equipment.last_seen:
                equipment.endpoint_status = 'unknown'
                continue
            delta_hours = (now - equipment.last_seen).total_seconds() / 3600.0
            if delta_hours <= ENDPOINT_STALE_HOURS:
                equipment.endpoint_status = 'online'
            elif delta_hours <= ENDPOINT_OFFLINE_HOURS:
                equipment.endpoint_status = 'stale'
            else:
                equipment.endpoint_status = 'offline'

    @api.depends('av_status', 'patch_status', 'encryption_enabled')
    def _compute_compliance_status(self):
        for equipment in self:
            if equipment.av_status == 'unknown' or equipment.patch_status == 'unknown':
                equipment.compliance_status = 'unknown'
            elif (equipment.av_status == 'protected' and equipment.patch_status == 'up_to_date'
                    and equipment.encryption_enabled):
                equipment.compliance_status = 'compliant'
            else:
                equipment.compliance_status = 'non_compliant'

    @api.model
    def _cron_refresh_endpoint_status(self):
        """endpoint_status depend de 'maintenant', pas seulement de
        last_seen - un poste peut passer signal-faible/hors-ligne sans
        qu'aucun champ ne change (meme raison que le cron SLA de l'ITSM)."""
        equipments = self.search([('last_seen', '!=', False)])
        equipments._compute_endpoint_status()
        self.env.cr.commit()
