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
    const dow = (d.getDay() + 6) % 7; // 0 = lundi
    d.setDate(d.getDate() - dow);
    d.setHours(0, 0, 0, 0);
    return d;
}
function daysBetween(a, b) {
    return Math.round((b - a) / 86400000);
}

const DAY_WIDTH = 32;
const ROW_HEIGHT = 36;
const WINDOW_DAYS = 42;
const NAV_STEP_DAYS = 21;

// Timeline/Gantt maison : Odoo Community n'a aucune vue Gantt native (c'est
// une fonctionnalite Enterprise), et project.task n'a meme pas de champ de
// debut planifie exploitable (date_end est la date de cloture reelle, pas
// une date prevue - d'ou l'ajout de date_start dans ce module). Tout est
// donc construit ici en HTML/CSS positionne (barres) + un SVG pour les
// fleches de dependance, pas de widget a reutiliser contrairement aux
// autres phases.
export class VillaNovaTimeline extends Component {
    static template = "villa_nova_project.Timeline";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.DAY_WIDTH = DAY_WIDTH;
        this.ROW_HEIGHT = ROW_HEIGHT;

        this.state = useState({
            loading: true,
            windowStart: startOfWeek(addDays(new Date(), -7)),
            tasks: [],
            drag: null,
        });
        this._taskRowIndex = {};
        this._suppressNextClick = false;

        onWillStart(() => this.loadTasks());
    }

    async loadTasks() {
        this.state.loading = true;
        const start = toISODate(this.state.windowStart);
        const end = toISODate(addDays(this.state.windowStart, WINDOW_DAYS));
        this.state.tasks = await this.orm.call("project.task", "get_timeline_data", [start, end]);
        this.state.loading = false;
    }

    get days() {
        const days = [];
        for (let i = 0; i < WINDOW_DAYS; i++) {
            days.push(addDays(this.state.windowStart, i));
        }
        return days;
    }

    get months() {
        const months = [];
        for (const d of this.days) {
            const key = `${d.getFullYear()}-${d.getMonth()}`;
            const last = months[months.length - 1];
            if (last && last.key === key) {
                last.count += 1;
            } else {
                months.push({ key, count: 1, label: d.toLocaleDateString("fr-FR", { month: "long", year: "numeric" }) });
            }
        }
        return months;
    }

    get gridWidth() {
        return this.days.length * DAY_WIDTH;
    }

    get todayOffset() {
        return daysBetween(this.state.windowStart, new Date()) * DAY_WIDTH;
    }

    get rows() {
        const groups = new Map();
        for (const t of this.state.tasks) {
            const key = t.project_id || 0;
            if (!groups.has(key)) {
                groups.set(key, { label: t.project_name || "Sans projet", tasks: [] });
            }
            groups.get(key).tasks.push(t);
        }
        const rows = [];
        const taskRowIndex = {};
        for (const group of groups.values()) {
            rows.push({ type: "group", label: group.label });
            for (const t of group.tasks) {
                taskRowIndex[t.id] = rows.length;
                const geometry = this._barGeometry(t);
                rows.push({ type: "task", task: t, ...geometry });
            }
        }
        this._taskRowIndex = taskRowIndex;
        return rows;
    }

    _barGeometry(t) {
        const drag = this.state.drag;
        if (drag && drag.taskId === t.id) {
            return { left: drag.previewLeft, width: drag.previewWidth, endLeft: drag.previewLeft + drag.previewWidth };
        }
        const start = new Date(t.date_start);
        const end = new Date(t.date_deadline);
        const left = daysBetween(this.state.windowStart, start) * DAY_WIDTH;
        const width = Math.max(DAY_WIDTH, (daysBetween(start, end) + 1) * DAY_WIDTH);
        return { left, width, endLeft: left + width };
    }

    // ------------------------------------------------------------------
    // Glisser-deposer : deplacer une barre entiere (mode "move") ou etirer
    // un bord (mode "resize-start"/"resize-end"). setPointerCapture sur
    // l'element cible garantit que pointermove/pointerup continuent
    // d'arriver meme si le curseur sort de la barre pendant le geste -
    // pas besoin d'ecouteurs globaux sur window.
    // ------------------------------------------------------------------
    onBarPointerDown(ev, task, mode) {
        ev.preventDefault();
        ev.stopPropagation();
        const geom = this._barGeometry(task);
        this.state.drag = {
            taskId: task.id,
            mode,
            pointerId: ev.pointerId,
            startClientX: ev.clientX,
            originLeft: geom.left,
            originWidth: geom.width,
            previewLeft: geom.left,
            previewWidth: geom.width,
        };
        ev.currentTarget.setPointerCapture(ev.pointerId);
    }

    onBarPointerMove(ev) {
        const drag = this.state.drag;
        if (!drag || ev.pointerId !== drag.pointerId) return;
        const deltaPx = ev.clientX - drag.startClientX;
        const deltaDays = Math.round(deltaPx / DAY_WIDTH);

        if (drag.mode === "move") {
            drag.previewLeft = drag.originLeft + deltaDays * DAY_WIDTH;
            drag.previewWidth = drag.originWidth;
        } else if (drag.mode === "resize-end") {
            drag.previewLeft = drag.originLeft;
            drag.previewWidth = Math.max(DAY_WIDTH, drag.originWidth + deltaDays * DAY_WIDTH);
        } else if (drag.mode === "resize-start") {
            const newWidth = Math.max(DAY_WIDTH, drag.originWidth - deltaDays * DAY_WIDTH);
            drag.previewLeft = drag.originLeft - (newWidth - drag.originWidth);
            drag.previewWidth = newWidth;
        }
    }

    async onBarPointerUp(ev) {
        const drag = this.state.drag;
        if (!drag || ev.pointerId !== drag.pointerId) return;
        this.state.drag = null;

        if (drag.previewLeft === drag.originLeft && drag.previewWidth === drag.originWidth) {
            return; // simple clic, pas un geste - laisse le clic ouvrir la tache
        }
        this._suppressNextClick = true;

        const newStart = addDays(this.state.windowStart, Math.round(drag.previewLeft / DAY_WIDTH));
        const newEnd = addDays(this.state.windowStart, Math.round((drag.previewLeft + drag.previewWidth) / DAY_WIDTH) - 1);

        const vals = {};
        if (drag.mode === "move" || drag.mode === "resize-start") {
            vals.date_start = toISODate(newStart);
        }
        if (drag.mode === "move" || drag.mode === "resize-end") {
            vals.date_deadline = toISODate(newEnd);
        }

        await this.orm.write("project.task", [drag.taskId], vals);
        await this.loadTasks();
    }

    onBarClick(taskId) {
        if (this._suppressNextClick) {
            this._suppressNextClick = false;
            return;
        }
        this.openTask(taskId);
    }

    get dependencyLines() {
        const rows = this.rows; // peuple _taskRowIndex avant lecture ci-dessous
        const byId = {};
        for (const t of this.state.tasks) byId[t.id] = t;

        const lines = [];
        for (const row of rows) {
            if (row.type !== "task") continue;
            const toRow = this._taskRowIndex[row.task.id];
            for (const blockerId of row.task.depend_on_ids) {
                const fromRow = this._taskRowIndex[blockerId];
                if (fromRow === undefined) continue;
                const blocker = byId[blockerId];
                const fromGeom = this._barGeometry(blocker);
                const midX = fromGeom.endLeft + 10;
                lines.push({
                    d: [
                        `M${fromGeom.endLeft},${fromRow * ROW_HEIGHT + ROW_HEIGHT / 2}`,
                        `L${midX},${fromRow * ROW_HEIGHT + ROW_HEIGHT / 2}`,
                        `L${midX},${toRow * ROW_HEIGHT + ROW_HEIGHT / 2}`,
                        `L${row.left},${toRow * ROW_HEIGHT + ROW_HEIGHT / 2}`,
                    ].join(" "),
                });
            }
        }
        return lines;
    }

    prevWindow() {
        this.state.windowStart = addDays(this.state.windowStart, -NAV_STEP_DAYS);
        this.loadTasks();
    }
    nextWindow() {
        this.state.windowStart = addDays(this.state.windowStart, NAV_STEP_DAYS);
        this.loadTasks();
    }
    goToday() {
        this.state.windowStart = startOfWeek(addDays(new Date(), -7));
        this.loadTasks();
    }

    openTask(taskId) {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "project.task",
            res_id: taskId,
            views: [[false, "form"]],
            target: "current",
        });
    }
}

registry.category("actions").add("villa_nova_project.timeline", VillaNovaTimeline);
