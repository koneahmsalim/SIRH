import base64
import os


def set_company_branding(env):
    """Applique le logo de marque (symbole graphite, lisible sur fond clair)
    a toutes les societes : utilise sur la page de connexion, les rapports
    PDF, le portail et partout ou res.company.logo est affiche."""
    module_dir = os.path.dirname(__file__)
    logo_path = os.path.join(module_dir, 'static', 'src', 'img', 'icon_mark.png')
    if not os.path.exists(logo_path):
        return
    with open(logo_path, 'rb') as f:
        logo_data = base64.b64encode(f.read())
    env['res.company'].search([]).write({'logo': logo_data})
