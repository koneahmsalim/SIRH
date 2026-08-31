import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const STATUS_LABELS = {
    on_track: "À jour",
    at_risk: "À risque",
    off_track: "En retard",
    done: "Atteint",
};
const STATUS_BADGE_CLASS = {
    on_track: "vn-badge-success",
    at_risk: "vn-badge-warning",
    off_track: "vn-badge-danger",
    done: "vn-badge-brand",
};

// Objectifs/OKR : fonctionnalite Asana totalement absente d'Odoo, aucune
// base a reutiliser. Meme pattern de carte que le Portfolio (villa_nova_project.goal
// est un modele nouveau et volontairement simple - un objectif, un
// responsable, une echeance, un avancement).
export class VillaNovaGoals extends Component {
    static template = "villa_nova_project.Goals";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.STATUS_LABELS = STATUS_LABELS;
        this.STATUS_BADGE_CLASS = STATUS_BADGE_CLASS;

        this.state = useState({ loading: true, goals: [] });
        onWillStart(() => this.load());
    }

    async load() {
        this.state.loading = true;
        this.state.goals = await this.orm.searchRead(
            "villa_nova_project.goal",
            [],
            ["id", "name", "owner_id", "target_date", "progress", "status", "project_ids"]
        );
        this.state.loading = false;
    }

    avatarUrl(userId) {
        return `/web/image/res.users/${userId}/avatar_128`;
    }

    openGoal(goalId) {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "villa_nova_project.goal",
            res_id: goalId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    createGoal() {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "villa_nova_project.goal",
            views: [[false, "form"]],
            target: "current",
        });
    }
}

registry.category("actions").add("villa_nova_project.goals", VillaNovaGoals);
