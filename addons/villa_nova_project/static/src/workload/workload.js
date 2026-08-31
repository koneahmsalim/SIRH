import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

function toISODate(d) {
    const pad = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}
function addDays(date, n) {
    const d = new Date(date);
    d.setDate(d.getDate() + n);
    return d;
}
function startOfWeek(date) {
    const d = new Date(date);
    const dow = (d.getDay() + 6) % 7;
    d.setDate(d.getDate() - dow);
    d.setHours(0, 0, 0, 0);
    return d;
}

const WINDOW_DAYS = 14;
const CAPACITY_HOURS_PER_DAY = 8;

// Charge de chaque personne, jour par jour : project.task n'a pas de suivi
// d'heures planifiees par defaut (le champ natif allocated_hours existe
// mais n'est renseigne par personne que si le PM le fait) - la repartition
// se fait ici en etalant les heures allouees d'une tache sur toute sa duree
// prevue, plutot que d'inventer une estimation.
export class VillaNovaWorkload extends Component {
    static template = "villa_nova_project.Workload";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.CAPACITY = CAPACITY_HOURS_PER_DAY;

        this.state = useState({
            loading: true,
            windowStart: startOfWeek(new Date()),
            raw: [],
        });

        onWillStart(() => this.load());
    }

    async load() {
        this.state.loading = true;
        const start = toISODate(this.state.windowStart);
        const end = toISODate(addDays(this.state.windowStart, WINDOW_DAYS - 1));
        this.state.raw = await this.orm.call("project.task", "get_workload_data", [start, end]);
        this.state.loading = false;
    }

    get days() {
        const days = [];
        for (let i = 0; i < WINDOW_DAYS; i++) {
            days.push(addDays(this.state.windowStart, i));
        }
        return days;
    }

    get rows() {
        const windowStart = this.state.windowStart;
        const windowEnd = addDays(windowStart, WINDOW_DAYS - 1);
        const users = new Map();

        for (const item of this.state.raw) {
            if (!users.has(item.user_id)) {
                users.set(item.user_id, { userId: item.user_id, userName: item.user_name, cells: {}, tasksByDay: {} });
            }
            const row = users.get(item.user_id);
            const start = new Date(item.date_start);
            const end = new Date(item.date_deadline);
            const from = start < windowStart ? windowStart : start;
            const to = end > windowEnd ? windowEnd : end;
            for (let d = new Date(from); d <= to; d = addDays(d, 1)) {
                const key = toISODate(d);
                row.cells[key] = (row.cells[key] || 0) + item.hours_per_day;
                (row.tasksByDay[key] || (row.tasksByDay[key] = [])).push(item.task_name);
            }
        }

        return [...users.values()].sort((a, b) => a.userName.localeCompare(b.userName, "fr"));
    }

    cellLoad(row, day) {
        const hours = row.cells[toISODate(day)] || 0;
        const ratio = hours / CAPACITY_HOURS_PER_DAY;
        let cls = "vn-workload-cell-empty";
        if (hours > 0 && ratio < 0.75) cls = "vn-workload-cell-light";
        else if (ratio >= 0.75 && ratio <= 1.05) cls = "vn-workload-cell-full";
        else if (ratio > 1.05) cls = "vn-workload-cell-over";
        return { hours, cls, tasks: row.tasksByDay[toISODate(day)] || [] };
    }

    prevWindow() {
        this.state.windowStart = addDays(this.state.windowStart, -WINDOW_DAYS);
        this.load();
    }
    nextWindow() {
        this.state.windowStart = addDays(this.state.windowStart, WINDOW_DAYS);
        this.load();
    }
    goToday() {
        this.state.windowStart = startOfWeek(new Date());
        this.load();
    }

    get weekLabel() {
        const start = this.state.windowStart;
        const end = addDays(start, WINDOW_DAYS - 1);
        const opts = { day: "numeric", month: "long" };
        return `${start.toLocaleDateString("fr-FR", opts)} — ${end.toLocaleDateString("fr-FR", { ...opts, year: "numeric" })}`;
    }
}

registry.category("actions").add("villa_nova_project.workload", VillaNovaWorkload);
