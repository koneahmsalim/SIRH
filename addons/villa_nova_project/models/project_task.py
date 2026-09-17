from odoo import api, fields, models, _


class ProjectTask(models.Model):
    _inherit = 'project.task'

    # Odoo Community n'a pas de champ de debut planifie sur les taches
    # (date_end = date de cloture reelle, pas une date prevue) - necessaire
    # pour tracer une barre dans la Timeline (villa_nova_project), pas
    # seulement un point d'echeance.
    date_start = fields.Datetime(
        string="Début planifié",
        help="Date de début prévue de la tâche, utilisée par la vue Timeline.",
    )

    def write(self, vals):
        res = super().write(vals)
        if 'state' in vals and self.project_id:
            # villa_nova_project.goal.progress depend de project.task via une
            # recherche directe (task_ids exclut nativement les taches
            # fermees, donc pas trackable par @api.depends) - on force le
            # recalcul explicitement au lieu de laisser l'objectif se figer.
            goals = self.env['villa_nova_project.goal'].sudo().search(
                [('project_ids', 'in', self.project_id.ids)])
            if goals:
                goals._compute_progress()
        return res

    @api.model
    def get_timeline_data(self, date_from, date_to):
        """Taches ayant une des deux dates (debut planifie ou echeance) et
        dont l'intervalle [debut, echeance] chevauche la fenetre visible.
        Sans date_start, l'echeance sert aussi de debut (barre d'un jour) -
        et inversement."""
        window_start = fields.Datetime.from_string(date_from)
        window_end = fields.Datetime.from_string(date_to)
        tasks = self.search([
            ('project_id', '!=', False),
            '|', ('date_start', '!=', False), ('date_deadline', '!=', False),
        ], order='project_id, date_start, date_deadline')

        result = []
        for task in tasks:
            start = task.date_start or task.date_deadline
            end = task.date_deadline or task.date_start
            if end < window_start or start > window_end:
                continue
            result.append({
                'id': task.id,
                'name': task.name,
                'project_id': task.project_id.id,
                'project_name': task.project_id.name,
                'date_start': fields.Datetime.to_string(start),
                'date_deadline': fields.Datetime.to_string(end),
                'state': task.state,
                'depend_on_ids': task.depend_on_ids.ids,
            })
        return result

    @api.model
    def get_workload_data(self, date_from, date_to):
        """Une ligne par (tache, assigne) avec ses dates - la repartition
        heures/jour et l'agregation par utilisateur se font cote client
        (comme pour la Timeline), pour ne faire qu'un seul appel serveur."""
        window_start = fields.Datetime.from_string(date_from)
        window_end = fields.Datetime.from_string(date_to)
        tasks = self.search([
            ('user_ids', '!=', False),
            ('state', 'not in', ['1_done', '1_canceled']),
            '|', ('date_start', '!=', False), ('date_deadline', '!=', False),
        ])

        result = []
        for task in tasks:
            start = task.date_start or task.date_deadline
            end = task.date_deadline or task.date_start
            if end < window_start or start > window_end:
                continue
            span_days = (end.date() - start.date()).days + 1
            hours_per_day = (task.allocated_hours or 0) / span_days if span_days else 0
            for user in task.user_ids:
                result.append({
                    'user_id': user.id,
                    'user_name': user.name,
                    'task_id': task.id,
                    'task_name': task.name,
                    'date_start': fields.Datetime.to_string(start),
                    'date_deadline': fields.Datetime.to_string(end),
                    'hours_per_day': hours_per_day,
                })
        return result

    def action_villa_nova_view_depend_on(self):
        """"Bloque par" (depend_on_ids) n'a nativement qu'un onglet dans le
        formulaire, pas de bouton statistique contrairement a "Bloque"
        (action_dependent_tasks juste a cote) - meme pattern, cote symetrique."""
        self.ensure_one()
        return {
            'res_model': 'project.task',
            'type': 'ir.actions.act_window',
            'context': {**self._context, 'search_default_open_tasks': True},
            'domain': [('id', 'in', self.depend_on_ids.ids)],
            'name': _('Bloqué par'),
            'view_mode': 'list,form,kanban,calendar,pivot,graph,activity',
        }

    # ------------------------------------------------------------------
    # Accueil (page d'accueil facon Asana)
    # ------------------------------------------------------------------
    @api.model
    def _villa_nova_libelle_periode(self, debut, fin):
        """'21 - 29 sept.' quand la tache a un debut planifie et une echeance,
        '29 sept.' quand elle n'a que l'echeance. Les equipes qui arrivent
        d'Asana y lisent la meme information qu'avant, au meme endroit."""
        import babel.dates

        def _fmt(d, avec_mois=True):
            if not d:
                return ''
            try:
                return babel.dates.format_date(d, "d MMM" if avec_mois else "d", locale='fr_FR')
            except Exception:
                return d.strftime('%d/%m')

        if debut and fin:
            if debut == fin:
                return _fmt(fin)
            # Meme mois : on n'ecrit le mois qu'une fois ("21 - 29 sept.").
            meme_mois = debut.month == fin.month and debut.year == fin.year
            return '%s - %s' % (_fmt(debut, not meme_mois), _fmt(fin))
        return _fmt(fin or debut)

    @api.model
    def _villa_nova_tache_accueil(self, task, today):
        debut = task.date_start.date() if task.date_start else None
        echeance = task.date_deadline.date() if task.date_deadline else None
        return {
            'id': task.id,
            'name': task.name,
            'project_id': task.project_id.id or False,
            'project_name': task.project_id.name or '',
            'project_color': task.project_id.color or 0,
            'date_label': self._villa_nova_libelle_periode(debut, echeance),
            'overdue': bool(echeance and echeance < today),
            'done': task.state == '1_done',
            'assignees': [u.name for u in task.user_ids],
        }

    @api.model
    def _villa_nova_debut_periode(self, periode, today):
        """Borne basse des statistiques d'en-tete. None = depuis toujours."""
        if periode == 'month':
            return today.replace(day=1)
        if periode == 'all':
            return None
        return fields.Date.subtract(today, days=today.weekday())  # semaine en cours

    @api.model
    def get_villa_nova_home_data(self, periode='week', limite=12):
        """Toute la page d'accueil en un seul appel.

        Odoo n'a pas d'ecran d'accueil pour les projets : on atterrit sur une
        liste ou un kanban, sans point de depart qui dise ou on en est. Les
        equipes qui migrent depuis Asana perdent le leur ; celui-ci reprend le
        meme decoupage (a venir / en retard / terminees) pour qu'elles ne
        soient pas depaysees.

        Les blocs optionnels ne sont calcules que s'ils sont actifs : afficher
        moins doit aussi couter moins, sinon le reglage n'a d'effet que visuel.
        """
        utilisateur = self.env.user
        today = fields.Date.context_today(self)
        ouvertes = [('state', 'not in', ['1_done', '1_canceled'])]
        miennes = [('user_ids', 'in', utilisateur.id)]

        en_retard = self.search(
            miennes + ouvertes + [('date_deadline', '<', today)],
            order='date_deadline', limit=limite)
        a_venir = self.search(
            miennes + ouvertes + ['|', ('date_deadline', '>=', today),
                                       ('date_deadline', '=', False)],
            order='date_deadline asc, priority desc', limit=limite)

        # "Terminees" : les 30 derniers jours. Sans borne, l'onglet finit par
        # afficher l'historique complet, ce qui n'aide personne.
        terminees = self.search(
            miennes + [('state', '=', '1_done'),
                       ('write_date', '>=', fields.Date.subtract(today, days=30))],
            order='write_date desc', limit=limite)

        # --- Statistiques de l'en-tete, sur la periode choisie ---
        debut = self._villa_nova_debut_periode(periode, today)
        domaine_faites = miennes + [('state', '=', '1_done')]
        if debut:
            domaine_faites.append(('write_date', '>=', debut))
        faites = self.search_count(domaine_faites)

        mes_projets = self.search(miennes).mapped('project_id')
        collaborateurs = self.search(
            [('project_id', 'in', mes_projets.ids)] + ouvertes
        ).mapped('user_ids') - utilisateur

        actifs = utilisateur.villa_nova_widgets_actifs()
        resultat = {
            'upcoming': [self._villa_nova_tache_accueil(t, today) for t in a_venir],
            'overdue': [self._villa_nova_tache_accueil(t, today) for t in en_retard],
            'completed': [self._villa_nova_tache_accueil(t, today) for t in terminees],
            'stats': {
                'done': faites,
                'collaborators': len(collaborateurs),
            },
            'widgets_actifs': actifs,
            'widgets_disponibles': self.env['res.users'].villa_nova_widgets_disponibles(),
            'selectable_projects': [
                {'id': p.id, 'name': p.name}
                for p in self.env['project.project'].search([('active', '=', True)], order='name')
            ],
            'projects': [],
            'goals': [],
            'health': [],
            'delegated': [],
        }

        if 'projets' in actifs:
            resultat['projects'] = self._villa_nova_widget_projets(today)
        if 'objectifs' in actifs:
            resultat['goals'] = self._villa_nova_widget_objectifs()
        if 'sante' in actifs:
            resultat['health'] = self._villa_nova_widget_sante()
        if 'confiees' in actifs:
            resultat['delegated'] = self._villa_nova_widget_confiees(today, limite)
        return resultat

    # ------------------------------------------------------------------
    # Blocs optionnels
    # ------------------------------------------------------------------
    @api.model
    def _villa_nova_widget_projets(self, today):
        ouvertes = [('state', 'not in', ['1_done', '1_canceled'])]
        bientot = fields.Date.add(today, days=7)
        liste = []
        for projet in self.env['project.project'].search(
                [('active', '=', True)], order='write_date desc', limit=6):
            taches = self.search([('project_id', '=', projet.id)] + ouvertes)
            datees = taches.filtered(lambda t: t.date_deadline)
            nb_retard = len(datees.filtered(lambda t: t.date_deadline.date() < today))
            nb_proches = len(datees.filtered(lambda t: today <= t.date_deadline.date() <= bientot))
            if nb_retard:
                sous_titre = '%d tâche%s en retard' % (nb_retard, 's' if nb_retard > 1 else '')
            elif nb_proches:
                sous_titre = '%d tâche%s à échéance proche' % (nb_proches, 's' if nb_proches > 1 else '')
            elif taches:
                sous_titre = '%d tâche%s en cours' % (len(taches), 's' if len(taches) > 1 else '')
            else:
                sous_titre = 'Aucune tâche ouverte'
            liste.append({
                'id': projet.id,
                'name': projet.name,
                'color': projet.color or 0,
                'overdue_count': nb_retard,
                'subtitle': sous_titre,
            })
        return liste

    @api.model
    def _villa_nova_widget_objectifs(self):
        Goal = self.env['villa_nova_project.goal']
        libelles = dict(Goal._fields['status'].selection)
        classes = {
            'on_track': 'vn-home-etat-ok',
            'at_risk': 'vn-home-etat-risque',
            'off_track': 'vn-home-etat-retard',
            'done': 'vn-home-etat-atteint',
        }
        objectifs = Goal.search([('active', '=', True)], order='target_date, id', limit=6)
        return [{
            'id': g.id,
            'name': g.name,
            'progress': int(round(g.progress or 0)),
            'status': g.status or 'on_track',
            'status_label': libelles.get(g.status, ''),
            'status_class': classes.get(g.status, 'vn-home-etat-ok'),
            'owner': g.owner_id.name or '',
        } for g in objectifs]

    @api.model
    def _villa_nova_widget_sante(self):
        libelles = {
            'on_track': "À jour", 'at_risk': "À risque",
            'late': "En retard", 'no_data': "Sans données",
        }
        classes = {
            'on_track': 'vn-home-etat-ok', 'at_risk': 'vn-home-etat-risque',
            'late': 'vn-home-etat-retard', 'no_data': 'vn-home-etat-neutre',
        }
        comptes = {'on_track': 0, 'at_risk': 0, 'late': 0, 'no_data': 0}
        for projet in self.env['project.project'].get_portfolio_data():
            comptes[projet['health']] = comptes.get(projet['health'], 0) + 1
        return [{
            'cle': cle,
            'libelle': libelles[cle],
            'classe': classes[cle],
            'nb': comptes.get(cle, 0),
        } for cle in ('late', 'at_risk', 'on_track', 'no_data')]

    @api.model
    def _villa_nova_widget_confiees(self, today, limite):
        """Ce que j'ai demande a d'autres et qui n'est pas fait. Asana l'offre
        sous "Tasks I've assigned" ; Odoo oblige a construire un filtre."""
        moi = self.env.user
        taches = self.search([
            ('create_uid', '=', moi.id),
            ('state', 'not in', ['1_done', '1_canceled']),
            ('user_ids', '!=', False),
            ('user_ids', 'not in', moi.id),
        ], order='date_deadline asc, id desc', limit=limite)
        return [self._villa_nova_tache_accueil(t, today) for t in taches]

    # ------------------------------------------------------------------
    # Actions rapides
    # ------------------------------------------------------------------
    @api.model
    def villa_nova_creer_tache(self, nom, project_id=False):
        """Creation en une ligne depuis l'accueil, sans formulaire.

        Sans projet, Odoo 18 cree une tache privee - c'est exactement le
        comportement d'Asana, ou une tache peut naitre dans "Mes taches" puis
        etre rattachee a un projet plus tard.
        """
        nom = (nom or '').strip()
        if not nom:
            return False
        valeurs = {'name': nom, 'user_ids': [(6, 0, [self.env.user.id])]}
        if project_id:
            valeurs['project_id'] = int(project_id)
        return self.create(valeurs).id

    def villa_nova_toggle_done(self):
        """Coche / decoche depuis l'accueil, sans ouvrir la tache - le geste
        de base d'Asana, que le kanban d'Odoo demande de faire par
        glisser-deposer dans une colonne."""
        for task in self:
            task.state = '01_in_progress' if task.state == '1_done' else '1_done'
        return True

    # ------------------------------------------------------------------
    # Boite de reception (equivalent de l'Inbox Asana)
    # ------------------------------------------------------------------
    @api.model
    def get_villa_nova_inbox_data(self, limite=40):
        """Ce qui attend une action de ma part, puis ce qui a bouge autour de moi.

        Asana concentre dans son Inbox les deux : les demandes qui me sont
        adressees et les commentaires sur mon travail. Odoo les separe - les
        activites d'un cote (systray "A faire"), le fil de discussion de
        chaque tache de l'autre - si bien qu'il faut ouvrir chaque tache pour
        savoir ce qui s'y est dit. On les reunit ici.
        """
        moi = self.env.user
        today = fields.Date.context_today(self)

        # --- 1. Activites qui me sont assignees, sur projets et taches ---
        activites = self.env['mail.activity'].search([
            ('user_id', '=', moi.id),
            ('res_model', 'in', ['project.task', 'project.project']),
        ], order='date_deadline', limit=limite)

        groupes = {'retard': [], 'aujourdhui': [], 'suite': []}
        for a in activites:
            echeance = a.date_deadline
            if echeance and echeance < today:
                cle = 'retard'
            elif echeance == today:
                cle = 'aujourdhui'
            else:
                cle = 'suite'
            enregistrement = self.env[a.res_model].browse(a.res_id).exists()
            groupes[cle].append({
                'id': a.id,
                'res_model': a.res_model,
                'res_id': a.res_id,
                'record_name': enregistrement.display_name if enregistrement else '(supprimé)',
                'project_name': (
                    enregistrement.project_id.name
                    if a.res_model == 'project.task' and enregistrement and enregistrement.project_id
                    else ''
                ),
                'type': a.activity_type_id.name or "Activité",
                'summary': a.summary or '',
                'date_label': self._villa_nova_libelle_periode(None, echeance),
                'overdue': bool(echeance and echeance < today),
            })

        # --- 2. Ce qui s'est dit recemment sur mes taches ---
        mes_taches = self.search([
            ('user_ids', 'in', moi.id),
            ('state', 'not in', ['1_canceled']),
        ])
        messages = self.env['mail.message'].search([
            ('model', '=', 'project.task'),
            ('res_id', 'in', mes_taches.ids),
            ('message_type', '=', 'comment'),
            ('author_id', '!=', moi.partner_id.id),
            ('date', '>=', fields.Datetime.subtract(fields.Datetime.now(), days=14)),
        ], order='date desc', limit=limite)

        import re
        fil = []
        for m in messages:
            tache = self.browse(m.res_id).exists()
            corps = re.sub(r'<[^>]+>', ' ', m.body or '')
            corps = re.sub(r'\s+', ' ', corps).strip()
            fil.append({
                'id': m.id,
                'res_id': m.res_id,
                'record_name': tache.display_name if tache else '(supprimée)',
                'project_name': tache.project_id.name if tache and tache.project_id else '',
                'author': m.author_id.name or "Système",
                'extrait': corps[:180],
                'date_label': self._villa_nova_libelle_periode(None, m.date.date()),
            })

        return {
            'a_traiter': groupes,
            'nb_a_traiter': sum(len(v) for v in groupes.values()),
            'fil': fil,
        }

    @api.model
    def villa_nova_terminer_activite(self, activity_id):
        """Solde une activite depuis la boite de reception, sans ouvrir la fiche."""
        activite = self.env['mail.activity'].browse(int(activity_id)).exists()
        if not activite:
            return False
        activite.action_feedback(feedback="Traité depuis la boîte de réception.")
        return True
