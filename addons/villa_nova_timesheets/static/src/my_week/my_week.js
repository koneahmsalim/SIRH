import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { user } from "@web/core/user";

const DAY_LABELS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"];
const QUICK_HOURS = [0.5, 1, 2, 4, 8];

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

// Feuille de temps hebdomadaire pensee comme un carnet, pas un tableur : une
// carte par jour plutot qu'une grille de cellules, saisie guidee (raccourcis
// d'heures, activites recentes en un clic) plutot que N colonnes a remplir a
// la main a chaque ligne - cf. retour utilisateur ("habitue a Excel mais le
// trouvait ennuyeux a remplir"). Reutilise entierement account.analytic.line
// et villa_nova_activity_id existants, aucun nouveau modele.
export class VillaNovaMyWeek extends Component {
    static template = "villa_nova_timesheets.MyWeek";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.actionService = useService("action");
        this.QUICK_HOURS = QUICK_HOURS;

        this.state = useState({
            loading: true,
            weekStart: startOfWeek(new Date()),
            employeeId: null,
            days: [],
            recentCombos: [],
            activities: [],
            projects: [],
            tasksByProject: {},
            openDay: null,
            deletingId: null,
            form: this._emptyForm(),
        });

        onWillStart(async () => {
            await this._loadStaticData();
            await this.loadWeek();
        });
    }

    _emptyForm() {
        return { project_id: null, task_id: null, activity_id: null, name: "", unit_amount: 1 };
    }

    get weekLabel() {
        const start = this.state.weekStart;
        const end = addDays(start, 6);
        const opts = { day: "numeric", month: "long" };
        const startStr = start.toLocaleDateString("fr-FR", opts);
        const endStr = end.toLocaleDateString("fr-FR", { day: "numeric", month: "long", year: "numeric" });
        return `${startStr} — ${endStr}`;
    }

    get weekTotal() {
        return this.state.days.reduce((sum, d) => sum + d.total, 0);
    }

    isToday(dateStr) {
        return dateStr === toISODate(new Date());
    }

    async _loadStaticData() {
        const employees = await this.orm.searchRead("hr.employee", [["user_id", "=", user.userId]], ["id"]);
        this.state.employeeId = employees[0] ? employees[0].id : null;

        this.state.activities = await this.orm.call("villa.nova.timesheet.activity", "get_activities_for_me", []);
        this.state.projects = await this.orm.searchRead(
            "project.project",
            [["allow_timesheets", "=", true]],
            ["id", "name"]
        );
    }

    async _loadTasksForProject(projectId) {
        if (!projectId || this.state.tasksByProject[projectId]) {
            return;
        }
        const tasks = await this.orm.searchRead(
            "project.task",
            [["project_id", "=", projectId]],
            ["id", "name"]
        );
        this.state.tasksByProject[projectId] = tasks;
    }

    async loadWeek() {
        if (!this.state.employeeId) {
            this.state.loading = false;
            return;
        }
        this.state.loading = true;
        const start = toISODate(this.state.weekStart);
        const end = toISODate(addDays(this.state.weekStart, 6));

        const [lines, recentLines] = await Promise.all([
            this.orm.searchRead(
                "account.analytic.line",
                [["employee_id", "=", this.state.employeeId], ["date", ">=", start], ["date", "<=", end]],
                ["id", "date", "project_id", "task_id", "villa_nova_activity_id", "name", "unit_amount"]
            ),
            this.orm.searchRead(
                "account.analytic.line",
                [
                    ["employee_id", "=", this.state.employeeId],
                    ["date", ">=", toISODate(addDays(this.state.weekStart, -60))],
                    ["project_id", "!=", false],
                ],
                ["project_id", "task_id", "villa_nova_activity_id"],
                { order: "date desc", limit: 200 }
            ),
        ]);

        // Preload tasks for projects already used this week, so the dropdown
        // is ready without an extra round-trip when editing.
        await Promise.all(
            [...new Set(lines.filter((l) => l.project_id).map((l) => l.project_id[0]))].map((pid) =>
                this._loadTasksForProject(pid)
            )
        );

        const days = [];
        for (let i = 0; i < 7; i++) {
            const dateObj = addDays(this.state.weekStart, i);
            const dateStr = toISODate(dateObj);
            const dayLines = lines.filter((l) => l.date === dateStr);
            days.push({
                index: i,
                date: dateStr,
                label: DAY_LABELS[i],
                dayNum: dateObj.getDate(),
                entries: dayLines,
                total: dayLines.reduce((s, l) => s + l.unit_amount, 0),
            });
        }
        this.state.days = days;

        // Combinaisons (projet, tache, activite) les plus utilisees
        // recemment : transforme 3 selections repetitives en 1 clic.
        const seen = new Map();
        for (const l of recentLines) {
            if (!l.project_id) continue;
            const key = `${l.project_id[0]}-${l.task_id ? l.task_id[0] : 0}-${
                l.villa_nova_activity_id ? l.villa_nova_activity_id[0] : 0
            }`;
            if (!seen.has(key)) {
                seen.set(key, {
                    count: 0,
                    project_id: l.project_id,
                    task_id: l.task_id,
                    villa_nova_activity_id: l.villa_nova_activity_id,
                });
            }
            seen.get(key).count += 1;
        }
        this.state.recentCombos = [...seen.values()].sort((a, b) => b.count - a.count).slice(0, 5);

        this.state.loading = false;
    }

    prevWeek() {
        this.state.weekStart = addDays(this.state.weekStart, -7);
        this.state.openDay = null;
        this.loadWeek();
    }
    nextWeek() {
        this.state.weekStart = addDays(this.state.weekStart, 7);
        this.state.openDay = null;
        this.loadWeek();
    }
    goToday() {
        this.state.weekStart = startOfWeek(new Date());
        this.state.openDay = null;
        this.loadWeek();
    }

    openAddForm(dayIndex) {
        this.state.openDay = dayIndex;
        this.state.form = this._emptyForm();
    }
    closeAddForm() {
        this.state.openDay = null;
    }

    async onProjectChange(ev) {
        const projectId = ev.target.value ? Number(ev.target.value) : null;
        this.state.form.project_id = projectId;
        this.state.form.task_id = null;
        if (projectId) {
            await this._loadTasksForProject(projectId);
        }
    }
    onTaskChange(ev) {
        this.state.form.task_id = ev.target.value ? Number(ev.target.value) : null;
    }
    onActivityChange(ev) {
        this.state.form.activity_id = ev.target.value ? Number(ev.target.value) : null;
    }
    onDescriptionChange(ev) {
        this.state.form.name = ev.target.value;
    }
    setHours(h) {
        this.state.form.unit_amount = h;
    }
    onHoursInput(ev) {
        const v = parseFloat(ev.target.value);
        this.state.form.unit_amount = isNaN(v) ? 0 : v;
    }

    applyCombo(combo) {
        this.state.form.project_id = combo.project_id ? combo.project_id[0] : null;
        this.state.form.task_id = combo.task_id ? combo.task_id[0] : null;
        this.state.form.activity_id = combo.villa_nova_activity_id ? combo.villa_nova_activity_id[0] : null;
        if (combo.project_id) {
            this._loadTasksForProject(combo.project_id[0]);
        }
    }

    tasksForCurrentProject() {
        const pid = this.state.form.project_id;
        return pid && this.state.tasksByProject[pid] ? this.state.tasksByProject[pid] : [];
    }

    async saveEntry(dayIndex) {
        const form = this.state.form;
        if (!form.unit_amount || form.unit_amount <= 0) {
            this.notification.add(_t("Indiquez un nombre d'heures supérieur à 0."), { type: "warning" });
            return;
        }
        const activity = this.state.activities.find((a) => a.id === form.activity_id);
        if (activity && activity.project_required === "oui" && !form.project_id) {
            this.notification.add(
                _t("Le code activité choisi exige un projet / mandat / client."),
                { type: "warning" }
            );
            return;
        }
        const day = this.state.days[dayIndex];
        const vals = {
            employee_id: this.state.employeeId,
            date: day.date,
            unit_amount: form.unit_amount,
            name: form.name || (activity ? activity.name : _t("Activité")),
        };
        if (form.project_id) vals.project_id = form.project_id;
        if (form.task_id) vals.task_id = form.task_id;
        if (form.activity_id) vals.villa_nova_activity_id = form.activity_id;

        await this.orm.create("account.analytic.line", [vals]);
        this.state.openDay = null;
        await this.loadWeek();
    }

    askDelete(lineId) {
        this.state.deletingId = this.state.deletingId === lineId ? null : lineId;
    }
    async confirmDelete(lineId) {
        await this.orm.unlink("account.analytic.line", [lineId]);
        this.state.deletingId = null;
        await this.loadWeek();
    }

    openFullList() {
        this.actionService.doAction("hr_timesheet.act_hr_timesheet_line", { clearBreadcrumbs: false });
    }
}

registry.category("actions").add("villa_nova_timesheets.my_week", VillaNovaMyWeek);
