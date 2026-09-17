import { Component, useState, useRef, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";

const PERIODES = [
    { cle: "week", libelle: "Ma semaine" },
    { cle: "month", libelle: "Ce mois-ci" },
    { cle: "all", libelle: "Depuis toujours" },
];
const CLE_FIXE = "mes_taches";

// Accueil du module projet, facon page d'accueil Asana : une salutation, mes
// taches regroupees par etat, et les blocs que chacun choisit d'afficher et de
// disposer. Odoo n'a pas d'ecran equivalent - on arrive directement sur une
// liste ou un kanban, sans point de depart qui dise "voila ou tu en es". Tout
// tient en un seul appel serveur plutot qu'un appel par bloc.
export class VillaNovaProjectHome extends Component {
    static template = "villa_nova_project.Home";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.champNouvelleTache = useRef("champNouvelleTache");
        this.PERIODES = PERIODES;
        this.CLE_FIXE = CLE_FIXE;

        this.state = useState({
            loading: true,
            onglet: "upcoming",
            periode: "week",
            panneauWidgets: false,
            saisieOuverte: false,
            nouveauNom: "",
            nouveauProjet: "",
            enCoursCreation: false,
            blocDeplace: null,
            blocSurvole: null,
            data: {
                upcoming: [], overdue: [], completed: [],
                projects: [], goals: [], health: [], delegated: [],
                selectable_projects: [], widgets_actifs: [], widgets_disponibles: [],
                stats: { done: 0, collaborators: 0 },
            },
        });

        onWillStart(async () => {
            await this.recharger();
        });
    }

    async recharger() {
        this.state.data = await this.orm.call(
            "project.task", "get_villa_nova_home_data", [], { periode: this.state.periode });
        this.state.loading = false;
    }

    // ------------------------------------------------------------------
    // En-tete
    // ------------------------------------------------------------------
    get salutation() {
        // L'heure du poste, pas celle du serveur : un "Bonsoir" affiche a
        // 14h parce que le serveur est ailleurs ferait tout de suite faux.
        const heure = new Date().getHours();
        const prenom = (user.name || "").trim().split(" ")[0] || "";
        if (heure < 12) {
            return `Bonjour, ${prenom}`;
        }
        if (heure < 18) {
            return `Bon après-midi, ${prenom}`;
        }
        return `Bonsoir, ${prenom}`;
    }

    get dateDuJour() {
        const libelle = new Intl.DateTimeFormat("fr-FR", {
            weekday: "long", day: "numeric", month: "long", year: "numeric",
        }).format(new Date());
        return libelle.charAt(0).toUpperCase() + libelle.slice(1);
    }

    get libelleStatTaches() {
        const suffixe = { week: "cette semaine", month: "ce mois-ci", all: "au total" }[this.state.periode];
        const nb = this.state.data.stats.done;
        return `tâche${nb > 1 ? "s" : ""} terminée${nb > 1 ? "s" : ""} ${suffixe}`;
    }

    async choisirPeriode(cle) {
        this.state.periode = cle;
        await this.recharger();
    }

    // ------------------------------------------------------------------
    // Blocs et disposition
    // ------------------------------------------------------------------
    get blocs() {
        return this.state.data.widgets_actifs || [];
    }

    titreBloc(cle) {
        const w = (this.state.data.widgets_disponibles || []).find((x) => x.cle === cle);
        return w ? w.libelle : cle;
    }

    estActif(cle) {
        return this.blocs.includes(cle);
    }

    basculerPanneauWidgets() {
        this.state.panneauWidgets = !this.state.panneauWidgets;
    }

    async basculerWidget(cle) {
        if (cle === CLE_FIXE) {
            return;  // "Mes taches" n'est pas retirable
        }
        const actifs = [...this.blocs];
        const i = actifs.indexOf(cle);
        if (i === -1) {
            actifs.push(cle);
        } else {
            actifs.splice(i, 1);
        }
        await this.enregistrerOrdre(actifs);
    }

    async enregistrerOrdre(ordre) {
        // On applique localement avant l'aller-retour serveur : sans cela le
        // bloc repart a sa place d'origine le temps de la reponse, et le
        // glisser-deposer donne l'impression de ne pas avoir pris.
        this.state.data.widgets_actifs = ordre;
        await this.orm.call("res.users", "villa_nova_enregistrer_widgets", [ordre]);
        await this.recharger();
    }

    // --- Glisser-deposer ---------------------------------------------
    debutDeplacement(cle, ev) {
        this.state.blocDeplace = cle;
        if (ev && ev.dataTransfer) {
            ev.dataTransfer.effectAllowed = "move";
            // Firefox exige une donnee pour demarrer le glisser.
            ev.dataTransfer.setData("text/plain", cle);
        }
    }

    survol(cle) {
        if (this.state.blocDeplace && cle !== this.state.blocDeplace) {
            this.state.blocSurvole = cle;
        }
    }

    async depot(cle) {
        const depart = this.state.blocDeplace;
        this.state.blocSurvole = null;
        this.state.blocDeplace = null;
        if (!depart || depart === cle) {
            return;
        }
        const ordre = [...this.blocs];
        const i = ordre.indexOf(depart);
        const j = ordre.indexOf(cle);
        if (i === -1 || j === -1) {
            return;
        }
        ordre.splice(i, 1);
        ordre.splice(j, 0, depart);
        await this.enregistrerOrdre(ordre);
    }

    finDeplacement() {
        this.state.blocDeplace = null;
        this.state.blocSurvole = null;
    }

    // ------------------------------------------------------------------
    // Onglets
    // ------------------------------------------------------------------
    get onglets() {
        const d = this.state.data;
        return [
            { cle: "upcoming", libelle: "À venir", nb: d.upcoming.length },
            { cle: "overdue", libelle: "En retard", nb: d.overdue.length, alerte: true },
            { cle: "completed", libelle: "Terminées", nb: d.completed.length },
        ];
    }

    get taches() {
        return this.state.data[this.state.onglet] || [];
    }

    get messageVide() {
        return {
            upcoming: "Rien à venir. Profitez-en.",
            overdue: "Aucune tâche en retard.",
            completed: "Rien de terminé sur les 30 derniers jours.",
        }[this.state.onglet];
    }

    choisirOnglet(cle) {
        this.state.onglet = cle;
    }

    // ------------------------------------------------------------------
    // Creation rapide
    // ------------------------------------------------------------------
    ouvrirSaisie() {
        this.state.saisieOuverte = true;
        // Le champ n'existe pas encore au moment du clic : on attend le rendu.
        setTimeout(() => this.champNouvelleTache.el && this.champNouvelleTache.el.focus(), 0);
    }

    fermerSaisie() {
        this.state.saisieOuverte = false;
        this.state.nouveauNom = "";
    }

    async validerSaisie() {
        const nom = (this.state.nouveauNom || "").trim();
        if (!nom || this.state.enCoursCreation) {
            return;
        }
        this.state.enCoursCreation = true;
        try {
            await this.orm.call("project.task", "villa_nova_creer_tache", [
                nom, this.state.nouveauProjet ? parseInt(this.state.nouveauProjet, 10) : false,
            ]);
            this.state.nouveauNom = "";
            // On reste en saisie : creer plusieurs taches d'affilee est le
            // geste courant, rouvrir le champ a chaque fois le casserait.
            await this.recharger();
            this.state.onglet = "upcoming";
            setTimeout(() => this.champNouvelleTache.el && this.champNouvelleTache.el.focus(), 0);
        } finally {
            this.state.enCoursCreation = false;
        }
    }

    surToucheSaisie(ev) {
        if (ev.key === "Enter") {
            this.validerSaisie();
        } else if (ev.key === "Escape") {
            this.fermerSaisie();
        }
    }

    // ------------------------------------------------------------------
    // Actions
    // ------------------------------------------------------------------
    async basculerTerminee(tache) {
        // Coche optimiste : l'aller-retour serveur dure quelques centaines de
        // millisecondes, pendant lesquelles une case qui ne bouge pas donne
        // l'impression que le clic n'a pas pris.
        tache.done = !tache.done;
        await this.orm.call("project.task", "villa_nova_toggle_done", [[tache.id]]);
        await this.recharger();
    }

    ouvrirTache(id) {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "project.task",
            res_id: id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    ouvrirProjet(id) {
        this.actionService.doActionButton({
            resModel: "project.project",
            resId: id,
            name: "action_view_tasks",
            type: "object",
        });
    }

    ouvrirObjectif(id) {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "villa_nova_project.goal",
            res_id: id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    creerProjet() {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "project.project",
            views: [[false, "form"]],
            target: "current",
        });
    }

    ouvrirMesTaches() {
        this.actionService.doAction("villa_nova_project.action_villa_nova_my_tasks");
    }

    ouvrirPortfolio() {
        this.actionService.doAction("villa_nova_project.action_villa_nova_portfolio");
    }

    ouvrirObjectifs() {
        this.actionService.doAction("villa_nova_project.action_villa_nova_goals");
    }
}

registry.category("actions").add("villa_nova_project.home", VillaNovaProjectHome);
