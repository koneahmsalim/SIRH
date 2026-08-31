import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { View } from "@web/views/view";
import { user } from "@web/core/user";

function toISODate(d) {
    const pad = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}
function addDays(date, n) {
    const d = new Date(date);
    d.setDate(d.getDate() + n);
    return d;
}

const OPEN_TASK = ["state", "not in", ["1_done", "1_canceled"]];

// "Mes taches" facon Asana : au lieu d'une seule liste plate ou d'un kanban
// par projet, on regroupe automatiquement par echeance en 4 sections
// scannables (contrairement aux "stades personnels" natifs d'Odoo, qui
// existent deja mais demandent de glisser soi-meme chaque tache dans une
// colonne - ici le classement est automatique, base sur date_deadline).
// Chaque section reutilise la vue liste native (edition inline, case a
// cocher, priorite) via le composant generique <View/>, seul le domaine
// change - meme pattern que villa_nova_timesheets/my_timesheets_week.
export class VillaNovaMyTasks extends Component {
    static template = "villa_nova_project.MyTasks";
    static components = { View };
    static props = ["*"];

    setup() {
        this.actionService = useService("action");
        const ctx = this.props.action.context;
        this.listViewId = ctx.default_list_view_id || false;
        this.searchViewId = ctx.default_search_view_id || false;

        const today = toISODate(new Date());
        const soon = toISODate(addDays(new Date(), 7));
        const mine = ["user_ids", "in", [user.userId]];

        this.sections = [
            {
                key: "today",
                title: "Aujourd'hui",
                hint: "En retard ou pour aujourd'hui",
                domain: [mine, OPEN_TASK, ["date_deadline", "!=", false], ["date_deadline", "<=", today]],
                context: { default_user_ids: [user.userId], default_date_deadline: today },
            },
            {
                key: "upcoming",
                title: "À venir",
                hint: "Les 7 prochains jours",
                domain: [mine, OPEN_TASK, ["date_deadline", ">", today], ["date_deadline", "<=", soon]],
                context: { default_user_ids: [user.userId], default_date_deadline: soon },
            },
            {
                key: "later",
                title: "Plus tard",
                hint: "Au-delà de 7 jours",
                domain: [mine, OPEN_TASK, ["date_deadline", ">", soon]],
                context: { default_user_ids: [user.userId] },
            },
            {
                key: "nodate",
                title: "Sans échéance",
                hint: null,
                domain: [mine, OPEN_TASK, ["date_deadline", "=", false]],
                context: { default_user_ids: [user.userId] },
            },
        ];
    }

    openFullList() {
        this.actionService.doAction("project.action_server_view_my_task", { clearBreadcrumbs: false });
    }
}

registry.category("actions").add("villa_nova_project.my_tasks", VillaNovaMyTasks);
