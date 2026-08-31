import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { View } from "@web/views/view";
import { user } from "@web/core/user";

function toISODate(d) {
    const pad = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}
function startOfWeek(date) {
    const d = new Date(date);
    const dow = (d.getDay() + 6) % 7; // 0 = lundi
    d.setDate(d.getDate() - dow);
    d.setHours(0, 0, 0, 0);
    return d;
}
function addDays(date, n) {
    const d = new Date(date);
    d.setDate(d.getDate() + n);
    return d;
}

// "Mes feuilles de temps" avec navigation semaine par semaine (meme
// disposition que "Ma semaine" : precedent / Cette semaine / suivant),
// plutot que la liste native filtree sur la seule semaine en cours ou
// regroupee en sections repliables. La vue liste standard (colonnes,
// edition inline, recherche) est reutilisee telle quelle en dessous.
export class VillaNovaMyTimesheetsWeek extends Component {
    static template = "villa_nova_timesheets.MyTimesheetsWeek";
    static components = { View };
    static props = ["*"];

    setup() {
        this.actionService = useService("action");
        this.state = useState({ weekStart: startOfWeek(new Date()) });
        this.listViewId = this.props.action.context.default_list_view_id || false;
        this.searchViewId = this.props.action.context.default_search_view_id || false;
    }

    get weekLabel() {
        const start = this.state.weekStart;
        const end = addDays(start, 6);
        const opts = { day: "numeric", month: "long" };
        const startStr = start.toLocaleDateString("fr-FR", opts);
        const endStr = end.toLocaleDateString("fr-FR", { day: "numeric", month: "long", year: "numeric" });
        return `${startStr} — ${endStr}`;
    }

    get isCurrentWeek() {
        return toISODate(this.state.weekStart) === toISODate(startOfWeek(new Date()));
    }

    get domain() {
        const start = toISODate(this.state.weekStart);
        const end = toISODate(addDays(this.state.weekStart, 6));
        return [
            ["user_id", "=", user.userId],
            ["project_id", "!=", false],
            ["date", ">=", start],
            ["date", "<=", end],
        ];
    }

    get viewContext() {
        return {
            is_timesheet: 1,
            is_my_timesheets: 1,
            default_date: this.isCurrentWeek ? toISODate(new Date()) : toISODate(this.state.weekStart),
        };
    }

    prevWeek() {
        this.state.weekStart = addDays(this.state.weekStart, -7);
    }
    nextWeek() {
        this.state.weekStart = addDays(this.state.weekStart, 7);
    }
    goCurrentWeek() {
        this.state.weekStart = startOfWeek(new Date());
    }

    openFullList() {
        this.actionService.doAction("hr_timesheet.act_hr_timesheet_line", { clearBreadcrumbs: false });
    }
}

registry.category("actions").add("villa_nova_timesheets.my_timesheets_week", VillaNovaMyTimesheetsWeek);
