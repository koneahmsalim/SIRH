import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const SECTIONS = [
    { cle: "retard", libelle: "En retard", alerte: true },
    { cle: "aujourdhui", libelle: "Aujourd'hui" },
    { cle: "suite", libelle: "Plus tard" },
];

// Boite de reception facon Asana : ce qui attend une action de ma part, puis
// ce qui a bouge autour de moi. Odoo separe les deux - les activites dans le
// systray, les commentaires dans le fil de chaque tache - ce qui oblige a
// ouvrir les taches une a une pour savoir ce qui s'y est dit.
export class VillaNovaProjectInbox extends Component {
    static template = "villa_nova_project.Inbox";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.SECTIONS = SECTIONS;
        this.state = useState({
            loading: true,
            data: { a_traiter: { retard: [], aujourdhui: [], suite: [] }, nb_a_traiter: 0, fil: [] },
        });
        onWillStart(async () => {
            await this.recharger();
        });
    }

    async recharger() {
        this.state.data = await this.orm.call("project.task", "get_villa_nova_inbox_data", []);
        this.state.loading = false;
    }

    sectionsRemplies() {
        return SECTIONS.filter((s) => (this.state.data.a_traiter[s.cle] || []).length);
    }

    lignes(cle) {
        return this.state.data.a_traiter[cle] || [];
    }

    async terminer(activite) {
        await this.orm.call("project.task", "villa_nova_terminer_activite", [activite.id]);
        await this.recharger();
    }

    ouvrirEnregistrement(modele, id) {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: modele,
            res_id: id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    retourAccueil() {
        this.actionService.doAction("villa_nova_project.action_villa_nova_home");
    }
}

registry.category("actions").add("villa_nova_project.inbox", VillaNovaProjectInbox);
