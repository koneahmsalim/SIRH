import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

// Vue "qui est la aujourd'hui" : la premiere question qu'une RH se pose en
// ouvrant l'app, jusqu'ici sans reponse en un coup d'oeil (seulement un
// export PDF/CSV via l'assistant Retards & absences). 3 groupes qui
// s'excluent - voir hr.employee.get_villa_nova_today_overview pour la regle
// exacte de classement.
export class VillaNovaTodayOverview extends Component {
    static template = "villa_nova_biometric_attendance.TodayOverview";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.state = useState({
            loading: true, date: "", isHoliday: false,
            present: [], late: [], absent: [], onLeave: [], unregistered: [],
            deviceAlert: false, deviceSince: null,
        });

        onWillStart(() => this.load());
    }

    async load() {
        this.state.loading = true;
        const data = await this.orm.call("hr.employee", "get_villa_nova_today_overview", []);
        this.state.date = data.date;
        this.state.isHoliday = data.is_holiday;
        this.state.present = data.present;
        this.state.late = data.late;
        this.state.absent = data.absent;
        this.state.onLeave = data.on_leave;
        this.state.unregistered = data.unregistered;
        // Liaison avec le boitier : quand elle est rompue, aucun pointage ne
        // remonte et tout le monde bascule en "Absent". On le signale plutot
        // que de laisser lire une information fausse.
        // Booleen precalcule plutot qu'une condition composee dans le
        // template : une expression composee dans un t-if se compile mal chez
        // OWL (element affiche mais gestionnaires non lies, sans erreur).
        const liaison = data.device_status || { reachable: true };
        this.state.deviceAlert = liaison.reachable === false;
        this.state.deviceSince = liaison.since || null;
        this.state.loading = false;
    }

    formatTime(datetimeStr) {
        if (!datetimeStr) {
            return "";
        }
        const d = new Date(datetimeStr.replace(" ", "T") + "Z");
        return d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
    }

    openEmployee(employeeId) {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "hr.employee",
            res_id: employeeId,
            view_mode: "form",
            views: [[false, "form"]],
            target: "current",
        });
    }

    // Depuis "En conge", ouvrir directement la demande de conge (dates,
    // type, justificatif) est plus utile a une RH que la fiche employe -
    // c'est l'info qu'elle vient chercher en cliquant sur cette ligne.
    openLeave(leaveId) {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "hr.leave",
            res_id: leaveId,
            view_mode: "form",
            views: [[false, "form"]],
            target: "current",
        });
    }
}

registry.category("actions").add("villa_nova_biometric_attendance.today_overview", VillaNovaTodayOverview);
