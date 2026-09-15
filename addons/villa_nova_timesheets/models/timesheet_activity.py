from odoo import api, fields, models


NATURE_ANALYTIQUE = [
    ('accompagnement_portefeuille', "Accompagnement portefeuille"),
    ('administration', "Administration"),
    ('administration_executive', "Administration exécutive"),
    ('amelioration_interne', "Amélioration interne"),
    ('audit_controle', "Audit et contrôle"),
    ('communication', "Communication"),
    ('comptabilite', "Comptabilité"),
    ('conformite', "Conformité"),
    ('coordination_interne', "Coordination interne"),
    ('developpement_commercial', "Développement commercial"),
    ('finance_interne', "Finance interne"),
    ('fiscalite', "Fiscalité"),
    ('formation', "Formation"),
    ('gouvernance', "Gouvernance"),
    ('innovation', "Innovation"),
    ('interne_productif', "Interne productif"),
    ('juridique', "Juridique"),
    ('management', "Management"),
    ('pilotage', "Pilotage"),
    ('pilotage_projet', "Pilotage projet"),
    ('production', "Production"),
    ('projet_interne', "Projet interne"),
    ('relations_externes', "Relations externes"),
    ('ressources_humaines', "Ressources humaines"),
    ('strategie', "Stratégie"),
    ('support', "Support"),
    ('support_it', "Support IT"),
    ('tresorerie', "Trésorerie"),
    ('vie_interne', "Vie interne"),
]

BILLABILITY_DEFAULT = [
    ('interne', "Interne"),
    ('non_facturable', "Non facturable"),
    ('selon_contrat', "Selon contrat"),
    ('selon_dossier', "Selon dossier"),
    ('selon_mandat', "Selon mandat"),
    ('selon_mission', "Selon mission"),
    ('selon_operation', "Selon opération"),
    ('selon_projet', "Selon projet"),
    ('selon_transaction', "Selon transaction"),
]

PROJECT_REQUIRED = [
    ('oui', "Oui"),
    ('non', "Non"),
    ('recommande', "Recommandé"),
]

VISIBILITY_SCOPE = [
    ('all', "Tous les employés"),
    ('managers', "Managers et responsables"),
    ('commercial', "Business Development / Commerciaux"),
    ('direction_generale', "Bureau du Président / Direction Générale"),
    ('department', "Départements spécifiques"),
    ('project', "Projets spécifiques"),
]


class VillaNovaTimesheetActivity(models.Model):
    _name = 'villa.nova.timesheet.activity'
    _description = "Code activité de feuille de temps (nomenclature IAG)"
    _order = 'code'
    _rec_name = 'display_name'

    code = fields.Char(required=True, index=True, help="Identifiant stable : ne jamais renommer ni réutiliser, désactiver plutôt que supprimer.")
    name = fields.Char(string="Libellé", required=True)
    display_name = fields.Char(compute='_compute_display_name', store=True)

    category_lvl1 = fields.Char(string="Catégorie niveau 1")
    category_lvl2 = fields.Char(string="Catégorie niveau 2")
    nature_analytique = fields.Selection(NATURE_ANALYTIQUE, string="Nature analytique")
    entity = fields.Char(string="Entité principale")

    visibility_scope = fields.Selection(VISIBILITY_SCOPE, string="Visibilité", default='department', required=True)
    department_ids = fields.Many2many('hr.department', string="Départements autorisés",
                                       help="Utilisé seulement si Visibilité = Départements spécifiques.")
    project_ids = fields.Many2many(
        'project.project', string="Projets concernés",
        help="Rattache le code a un ou plusieurs projets. Avec Visibilite = "
             "Projets specifiques, seuls les membres de ces projets le voient "
             "proposé ; le code reste utilisable sur n'importe quelle ligne, "
             "c'est la suggestion qui est ciblee, pas une interdiction.",
    )
    a_valider = fields.Boolean(
        string="À valider par la RH", default=False, index=True,
        help="Code cree par un collaborateur faute de code existant adapte. Il "
             "est utilisable immediatement : la validation sert a tenir la "
             "nomenclature a jour, pas a bloquer la saisie.",
    )
    created_by_employee_id = fields.Many2one(
        'hr.employee', string="Proposé par", readonly=True,
        help="Collaborateur a l'origine de la proposition, pour pouvoir le "
             "recontacter lors de l'arbitrage.",
    )
    profile_description = fields.Char(string="Profil / population (texte du référentiel)")

    billability_default = fields.Selection(BILLABILITY_DEFAULT, string="Facturabilité par défaut", default='non_facturable')
    project_required = fields.Selection(PROJECT_REQUIRED, string="Projet requis", default='non')
    expected_deliverable = fields.Char(string="Livrable / preuve attendue")

    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('code_unique', 'unique(code)', "Ce code activité existe déjà."),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        """Un code cree par un collaborateur ordinaire part en "a valider".

        L'objectif est qu'une saisie de temps ne soit jamais bloquee faute de
        code adapte : le collaborateur cree le sien et continue. Mais une
        nomenclature ou 57 personnes ajoutent librement des codes derive en
        quelques semaines (doublons, libelles incoherents, codes jamais
        reutilises). Le marqueur permet donc a la RH de consolider APRES coup,
        sans jamais interrompre la saisie - le code est utilisable des sa
        creation.
        """
        approbateur = self.env.user.has_group('hr_timesheet.group_hr_timesheet_approver')
        employe = self.env.user.employee_id
        for vals in vals_list:
            if not approbateur:
                vals.setdefault('a_valider', True)
                if employe:
                    vals.setdefault('created_by_employee_id', employe.id)
        return super().create(vals_list)

    def action_valider_code(self):
        """Reprise en main du code par la RH : il rejoint la nomenclature."""
        self.write({'a_valider': False})

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"[{rec.code}] {rec.name}" if rec.code else rec.name

    def _is_visible_for_employee(self, employee):
        self.ensure_one()
        if self.visibility_scope == 'all':
            return True
        if self.visibility_scope == 'managers':
            # has_group() exige un utilisateur unique (ensure_one interne) :
            # un employe sans compte utilisateur lie (employee.user_id vide)
            # le fait planter - reproduit en listant "Toutes les feuilles de
            # temps", qui evalue la visibilite pour chaque employe present
            # dans les lignes, y compris ceux sans compte Odoo.
            return bool(employee.child_ids) or bool(
                employee.user_id and employee.user_id.has_group('hr_timesheet.group_hr_timesheet_approver')
            )
        if self.visibility_scope == 'direction_generale':
            return bool(
                employee.user_id and employee.user_id.has_group('villa_nova_recruitment.group_direction_generale')
            )
        if self.visibility_scope == 'commercial':
            return employee.department_id.name in ('Entités Commerciales', 'Ventes')
        if self.visibility_scope == 'department':
            return employee.department_id in self.department_ids
        if self.visibility_scope == 'project':
            # Membre de l'un des projets rattaches, a quelque titre que ce soit
            # (equipe ou responsable) : on ne veut pas qu'un code projet
            # disparaisse pour le chef de projet lui-meme.
            if not employee.user_id:
                return False
            return bool(self.project_ids.filtered(
                lambda p: employee.user_id in (p.user_id | p.message_partner_ids.user_ids)
            ))
        return False

    @api.model
    def _get_available_for_employee(self, employee):
        activities = self.search([])
        return activities.filtered(lambda a: a._is_visible_for_employee(employee))

    @api.model
    def get_activities_for_me(self):
        """Codes activite disponibles pour l'utilisateur courant, au format
        leger utilise par l'interface "Ma semaine" (villa_nova_timesheets).
        Reutilise _get_available_for_employee plutot que de dupliquer la
        logique de visibilite (departement/groupe) cote client."""
        employee = self.env.user.employee_id
        if not employee:
            return []
        activities = self._get_available_for_employee(employee)
        return activities.read([
            'id', 'display_name', 'code', 'name', 'project_required',
            'category_lvl1', 'a_valider',
        ])
