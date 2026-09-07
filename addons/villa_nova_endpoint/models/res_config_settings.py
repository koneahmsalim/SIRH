from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    """Point de configuration UNIQUE pour l'integration controle a distance -
    Odoo reste un wrapper fin (stocke juste l'identifiant MeshCentral du
    poste + genere un lien) plutot que de reimplementer du partage d'ecran/
    de la prise de main a distance (decision d'architecture confirmee avec
    l'utilisateur pour cette Phase 8 : MeshCentral auto-heberge, pas de
    solution maison). Le gabarit d'URL est configurable (pas code en dur)
    car le format exact du lien profond depend de la version/configuration
    MeshCentral de l'admin, jamais verifie en conditions reelles depuis cet
    environnement de developpement (pas d'instance MeshCentral disponible
    ici) - voir README du module."""
    _inherit = 'res.config.settings'

    meshcentral_url_template = fields.Char(
        string="Modèle d'URL MeshCentral", config_parameter='villa_nova_endpoint.meshcentral_url_template',
        help="URL vers l'interface MeshCentral pour ouvrir directement un poste, avec {node_id} "
             "comme espace réservé remplacé par l'identifiant MeshCentral du poste. "
             "Ex. https://mesh.infinity-africa.com/?viewmode=13&gotonode={node_id}",
    )
