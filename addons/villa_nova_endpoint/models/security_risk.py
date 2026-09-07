from odoo import api, fields, models

# Familles Windows dont le support de securite est termine cote editeur -
# liste MAINTENUE A LA MAIN, a mettre a jour periodiquement (pas une source
# vivante type flux CVE). Windows 10 grand public a atteint sa fin de
# support le 14 octobre 2025 : inclus ici, distinct des editions LTSC/IoT
# qui suivent un calendrier different et que cette heuristique simple ne
# distingue pas - un faux positif occasionnel est possible, a verifier au
# cas par cas plutot que de complexifier la detection pour un cas marginal.
EOL_OS_KEYWORDS = (
    'windows xp', 'windows vista', 'windows 7', 'windows 8',
    'windows server 2003', 'windows server 2008', 'windows server 2012',
    'windows 10',
)

RISK_LEVEL_SELECTION = [
    ('critical', "Critique"),
    ('high', "Élevé"),
    ('medium', "Moyen"),
    ('low', "Faible"),
    ('unknown', "Inconnu"),
]


class MaintenanceEquipmentSecurityRisk(models.Model):
    """Score de risque simple, construit UNIQUEMENT a partir de donnees deja
    remontees par l'agent (OS, patch_status, av_status, chiffrement) - PAS un
    scanner de vulnerabilites CVE (perimetre hors de portee de cette phase,
    necessiterait un flux de donnees externe maintenu et une correlation
    logicielle installee/version par version, un projet a part entiere).
    Objectif : donner un triage actionnable ("quels postes regarder en
    premier"), pas un audit de securite exhaustif - a presenter comme tel a
    l'utilisateur, jamais comme une garantie d'absence de vulnerabilite."""
    _inherit = 'maintenance.equipment'

    is_eol_os = fields.Boolean(string="OS en fin de support", compute='_compute_security_risk', store=True)
    security_risk_level = fields.Selection(
        RISK_LEVEL_SELECTION, string="Niveau de risque", compute='_compute_security_risk',
        store=True, index=True,
    )

    @api.depends('os_name', 'patch_status', 'av_status', 'encryption_enabled', 'endpoint_agent_id')
    def _compute_security_risk(self):
        for equipment in self:
            os_name = (equipment.os_name or '').lower()
            equipment.is_eol_os = any(keyword in os_name for keyword in EOL_OS_KEYWORDS)

            if not equipment.endpoint_agent_id:
                # Pas d'agent => pas de donnees fiables recentes, distinct
                # d'un poste avec agent dont les signaux sont juste absents.
                equipment.security_risk_level = 'unknown'
            elif equipment.is_eol_os:
                # Plus aucun correctif de securite possible, quelle que soit
                # la posture par ailleurs - toujours le niveau le plus grave.
                equipment.security_risk_level = 'critical'
            elif equipment.patch_status == 'overdue' or equipment.av_status == 'at_risk':
                equipment.security_risk_level = 'high'
            elif (equipment.patch_status in ('pending', 'unknown')
                    or equipment.av_status == 'unknown' or not equipment.encryption_enabled):
                equipment.security_risk_level = 'medium'
            elif equipment.patch_status == 'up_to_date' and equipment.av_status == 'protected':
                equipment.security_risk_level = 'low'
            else:
                equipment.security_risk_level = 'unknown'
