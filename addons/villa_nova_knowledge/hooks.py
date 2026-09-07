# website.menu est cree dynamiquement par le module website / le
# constructeur de site (pas d'ID externe stable exploitable en XML
# statique) - on retrouve le menu principal du site et on y ajoute les
# liens self-service par code, de facon idempotente (verifie par url
# avant de creer).

SELFSERVICE_LINKS = [
    ("Mes tickets", "/my/tickets", 55),
    ("Base de connaissances", "/my/knowledge", 56),
    ("Catalogue de services", "/my/services", 57),
]


def _add_selfservice_menu_links(env):
    Menu = env['website.menu']
    for website in env['website'].search([]):
        main_menu = Menu.search([('website_id', '=', website.id), ('parent_id', '=', False)], limit=1)
        if not main_menu:
            continue
        for name, url, sequence in SELFSERVICE_LINKS:
            exists = Menu.search([
                ('website_id', '=', website.id), ('parent_id', '=', main_menu.id), ('url', '=', url),
            ], limit=1)
            if exists:
                continue
            Menu.create({
                'name': name,
                'url': url,
                'parent_id': main_menu.id,
                'website_id': website.id,
                'sequence': sequence,
            })


def post_init(env):
    _add_selfservice_menu_links(env)
