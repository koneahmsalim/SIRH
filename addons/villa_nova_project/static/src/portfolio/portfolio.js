import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const HEALTH_LABELS = {
    on_track: "À jour",
    at_risk: "À risque",
    late: "En retard",
    no_data: "Pas de données",
};
const HEALTH_BADGE_CLASS = {
    on_track: "vn-badge-success",
    at_risk: "vn-badge-warning",
    late: "vn-badge-danger",
    no_data: "vn-badge-neutral",
};

// Portfolio : vue transverse sur tous les projets actifs, equivalent des
// Portfolios Asana (fonctionnalite payante chez eux). La sante de chaque
// projet est calculee automatiquement (taux de taches en retard, proximite
// de l'echeance) plutot que de dependre d'une saisie manuelle - voir
// project.project.get_portfolio_data.
export class VillaNovaPortfolio extends Component {
    static template = "villa_nova_project.Portfolio";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.HEALTH_LABELS = HEALTH_LABELS;
        this.HEALTH_BADGE_CLASS = HEALTH_BADGE_CLASS;

        this.state = useState({ loading: true, projects: [] });

        onWillStart(async () => {
            this.state.projects = await this.orm.call("project.project", "get_portfolio_data", []);
            this.state.loading = false;
        });
    }

    get summary() {
        const counts = { on_track: 0, at_risk: 0, late: 0, no_data: 0 };
        for (const p of this.state.projects) {
            counts[p.health] = (counts[p.health] || 0) + 1;
        }
        return counts;
    }

    avatarUrl(userId) {
        return `/web/image/res.users/${userId}/avatar_128`;
    }

    openProject(projectId) {
        this.actionService.doActionButton({
            resModel: "project.project",
            resId: projectId,
            name: "action_view_tasks",
            type: "object",
        });
    }
}

registry.category("actions").add("villa_nova_project.portfolio", VillaNovaPortfolio);
