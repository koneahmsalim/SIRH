import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";

const STATE_LABELS = {
    new: "Nouveau", assigned: "Assigné", in_progress: "En cours",
    pending: "En attente", resolved: "Résolu", closed: "Clôturé", cancelled: "Annulé",
};
const PRIORITY_BADGE = { critical: "vn-badge-danger", high: "vn-badge-warning", medium: "vn-badge-info", low: "vn-badge-neutral" };
const PRIORITY_LABELS = { critical: "Critique", high: "Haute", medium: "Moyenne", low: "Basse" };

export class VillaNovaItsmDashboard extends Component {
    static template = "villa_nova_itsm.Dashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.STATE_LABELS = STATE_LABELS;
        this.PRIORITY_BADGE = PRIORITY_BADGE;
        this.PRIORITY_LABELS = PRIORITY_LABELS;

        this.state = useState({
            loading: true,
            counts: { open: 0, critical: 0, unassigned: 0, assigned_to_me: 0, sla_at_risk: 0, sla_breached: 0 },
            myTickets: [],
        });

        onWillStart(async () => {
            const data = await this.orm.call("itsm.ticket", "get_villa_nova_itsm_dashboard", []);
            this.state.counts = data.counts;
            this.state.myTickets = data.my_tickets;
            this.state.loading = false;
        });
    }

    openTickets(domain, name) {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name,
            res_model: "itsm.ticket",
            view_mode: "kanban,list,form",
            views: [[false, "kanban"], [false, "list"], [false, "form"]],
            domain,
        });
    }

    openOpenTickets() {
        this.openTickets([["state", "not in", ["closed", "cancelled"]]], "Tickets ouverts");
    }

    openCriticalTickets() {
        this.openTickets([["state", "not in", ["closed", "cancelled"]], ["priority", "=", "critical"]], "Tickets critiques");
    }

    openUnassignedTickets() {
        this.openTickets([["state", "not in", ["closed", "cancelled"]], ["user_id", "=", false]], "Tickets non assignés");
    }

    openMyTickets() {
        this.openTickets([["state", "not in", ["closed", "cancelled"]], ["user_id", "=", user.userId]], "Mes tickets");
    }

    openSlaAtRisk() {
        this.openTickets([
            ["state", "not in", ["closed", "cancelled"]],
            "|", ["sla_response_status", "=", "at_risk"], ["sla_resolution_status", "=", "at_risk"],
        ], "SLA à risque");
    }

    openSlaBreached() {
        this.openTickets([
            ["state", "not in", ["closed", "cancelled"]],
            "|", ["sla_response_status", "=", "breached"], ["sla_resolution_status", "=", "breached"],
        ], "SLA dépassé");
    }

    openTicket(ticketId) {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "itsm.ticket",
            res_id: ticketId,
            views: [[false, "form"]],
            target: "current",
        });
    }
}

registry.category("actions").add("villa_nova_itsm.dashboard", VillaNovaItsmDashboard);
