from odoo import api, fields, models

# Blocs de l'accueil. Le quatrieme element dit si le bloc est retirable :
# "Mes taches" est le coeur de l'ecran, il se deplace mais ne se retire pas -
# comme "My tasks" chez Asana.
WIDGETS_DISPONIBLES = [
    ('mes_taches', "Mes tâches", "Vos tâches par échéance. Toujours affiché.", True),
    ('projets', "Projets", "Les projets récents et leur état d'avancement.", False),
    ('objectifs', "Objectifs", "Vos objectifs et leur progression.", False),
    ('sante', "Santé des projets", "Répartition à jour / à risque / en retard.", False),
    ('confiees', "Tâches que j'ai confiées",
     "Les tâches ouvertes que vous avez assignées à d'autres.", False),
]
CLE_FIXE = 'mes_taches'
WIDGETS_PAR_DEFAUT = 'mes_taches,projets'


class ResUsers(models.Model):
    _inherit = 'res.users'

    # Stocke sur l'utilisateur plutot que dans le navigateur : la
    # configuration suit la personne d'un poste a l'autre, et reste lisible
    # cote serveur. L'ORDRE de la liste est significatif - c'est lui qui fixe
    # la disposition des blocs, modifiable par glisser-deposer.
    villa_nova_home_widgets = fields.Char(
        string="Blocs de l'accueil projet",
        default=WIDGETS_PAR_DEFAUT,
        help="Clés des blocs affichés sur l'accueil du module projet, dans l'ordre, "
             "séparées par des virgules.",
    )

    @api.model
    def villa_nova_widgets_disponibles(self):
        return [{'cle': c, 'libelle': l, 'aide': a, 'fixe': f}
                for c, l, a, f in WIDGETS_DISPONIBLES]

    @api.model
    def villa_nova_enregistrer_widgets(self, cles):
        """Les cles inconnues sont ecartees : la valeur vient du navigateur, on
        ne la recopie pas telle quelle en base. "Mes taches" est reinsere s'il
        manque, pour qu'aucun reglage ne puisse produire un accueil vide."""
        connues = [c for c, _l, _a, _f in WIDGETS_DISPONIBLES]
        retenues = []
        for c in (cles or []):
            if c in connues and c not in retenues:
                retenues.append(c)
        if CLE_FIXE not in retenues:
            retenues.insert(0, CLE_FIXE)
        self.env.user.sudo().write({'villa_nova_home_widgets': ','.join(retenues)})
        return retenues

    def villa_nova_widgets_actifs(self):
        self.ensure_one()
        brut = self.villa_nova_home_widgets
        if not brut:
            brut = WIDGETS_PAR_DEFAUT
        connues = [c for c, _l, _a, _f in WIDGETS_DISPONIBLES]
        actifs = []
        for c in brut.split(','):
            if c in connues and c not in actifs:
                actifs.append(c)
        if CLE_FIXE not in actifs:
            actifs.insert(0, CLE_FIXE)
        return actifs
