import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { imageUrl } from "@web/core/utils/urls";
import { _t } from "@web/core/l10n/translation";
import { user } from "@web/core/user";
import { VnBarChart } from "../bar_chart/bar_chart";

// Les methodes RPC ci-dessous appartiennent au module hrms_dashboard
// (models/hr_employee.py) : ce dashboard reutilise entierement la logique
// metier existante, il ne fait que la restituer avec une UI/UX repensee -
// voir le plan de refonte (aucun changement de modele/champ/droit).
export class VillaNovaDashboard extends Component {
    static template = "villa_nova_dashboard.Dashboard";
    static components = { VnBarChart };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.imageUrl = imageUrl;

        this.state = useState({
            loading: true,
            isManager: false,
            employee: null,
            upcoming: { birthday: [], event: [], announcement: [] },
            deptChart: [],
            leaveTrend: [],
            checkingInOut: false,
        });

        onWillStart(() => this.loadAll());
    }

    async loadAll() {
        this.state.loading = true;
        const [isManager, employeeRows, upcoming, deptChart, leaveTrend] = await Promise.all([
            this.orm.call("hr.employee", "check_user_group", []),
            this.orm.call("hr.employee", "get_user_employee_details", []),
            this.orm.call("hr.employee", "get_upcoming", []),
            this.orm.call("hr.employee", "get_dept_employee", []),
            this.orm.call("hr.employee", "employee_leave_trend", []),
        ]);
        this.state.isManager = isManager;
        this.state.employee = employeeRows ? employeeRows[0] : null;
        this.state.upcoming = upcoming;
        this.state.deptChart = deptChart;
        this.state.leaveTrend = leaveTrend.map((row) => ({ label: row.l_month, value: row.leave }));
        this.state.loading = false;
    }

    get greeting() {
        const hour = new Date().getHours();
        if (hour < 12) return _t("Bonjour");
        if (hour < 18) return _t("Bon après-midi");
        return _t("Bonsoir");
    }

    get todayLabel() {
        return new Date().toLocaleDateString("fr-FR", {
            weekday: "long",
            year: "numeric",
            month: "long",
            day: "numeric",
        });
    }

    get firstName() {
        const name = this.state.employee?.name || "";
        return name.split(" ")[0] || name;
    }

    get avatarUrl() {
        const emp = this.state.employee;
        return emp ? this.imageUrl("hr.employee", emp.id, "avatar_128", { unique: true }) : "";
    }

    get isCheckedIn() {
        return this.state.employee?.attendance_state === "checked_in";
    }

    get todayLeaveCount() {
        return this.state.employee?.leaves_today?.[0]?.[0] || 0;
    }

    get monthLeaveCount() {
        return this.state.employee?.leaves_this_month?.[0]?.[0] || 0;
    }

    get leavesToApproveCount() {
        return this.state.employee?.leaves_to_approve || 0;
    }

    get allocationsToApproveCount() {
        return this.state.employee?.leaves_alloc_req || 0;
    }

    get myTimesheetsCount() {
        return this.state.employee?.emp_timesheets || 0;
    }

    get openApplicationsCount() {
        return this.state.employee?.job_applications || 0;
    }

    get deptChartData() {
        return this.state.deptChart.map((row) => ({ label: row.label, value: row.value }));
    }

    async toggleAttendance() {
        if (this.state.checkingInOut || !this.state.employee) {
            return;
        }
        this.state.checkingInOut = true;
        try {
            await this.orm.call("hr.employee", "attendance_manual", [[this.state.employee.id]]);
            await this.loadAll();
        } finally {
            this.state.checkingInOut = false;
        }
    }

    openWindowAction(resModel, { name, domain, context, viewMode } = {}) {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name,
            res_model: resModel,
            view_mode: viewMode || "list,form",
            views: viewMode
                ? viewMode.split(",").map((v) => [false, v === "tree" ? "list" : v])
                : [[false, "list"], [false, "form"]],
            domain: domain || [],
            context: context || {},
            target: "current",
        });
    }

    openLeavesToApprove() {
        this.openWindowAction("hr.leave", {
            name: _t("Congés à approuver"),
            domain: [["state", "in", ["confirm", "validate1"]]],
        });
    }

    openAllocationsToApprove() {
        this.openWindowAction("hr.leave.allocation", {
            name: _t("Allocations à approuver"),
            domain: [["state", "in", ["confirm", "validate1"]]],
        });
    }

    openApplications() {
        this.openWindowAction("hr.applicant", {
            name: _t("Candidatures"),
            viewMode: "kanban,list,form",
        });
    }

    openMyTimesheets() {
        this.openWindowAction("account.analytic.line", {
            name: _t("Mes feuilles de temps"),
            domain: [["project_id", "!=", false], ["user_id", "=", user.userId]],
        });
    }

    statusBadgeClass(stateLabel) {
        const success = ["Approved", "Done"];
        const warning = ["To Approve", "Second Approval", "Submitted"];
        const danger = ["Cancelled", "Refused"];
        const info = ["To Report", "To Submit"];
        if (success.includes(stateLabel)) return "vn-badge-success";
        if (warning.includes(stateLabel)) return "vn-badge-warning";
        if (danger.includes(stateLabel)) return "vn-badge-danger";
        if (info.includes(stateLabel)) return "vn-badge-info";
        return "vn-badge-neutral";
    }

    openLeavesToday() {
        const today = new Date().toISOString().slice(0, 10);
        this.openWindowAction("hr.leave", {
            name: _t("En congé aujourd'hui"),
            domain: [["date_from", "<=", today], ["date_to", ">=", today], ["state", "=", "validate"]],
        });
    }
}

registry.category("actions").add("villa_nova_dashboard", VillaNovaDashboard);
