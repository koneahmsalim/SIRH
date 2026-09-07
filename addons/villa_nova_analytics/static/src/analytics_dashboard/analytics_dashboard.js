import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const PRIORITY_LABELS = { critical: "Critique", high: "Haute", medium: "Moyenne", low: "Basse" };
const PRIORITY_ORDER = ["critical", "high", "medium", "low"];

const CHART_W = 600;
const CHART_H = 140;
const CHART_PAD = 12;

export class VillaNovaAnalyticsDashboard extends Component {
    static template = "villa_nova_analytics.Dashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.PRIORITY_LABELS = PRIORITY_LABELS;
        this.PRIORITY_ORDER = PRIORITY_ORDER;
        this.CHART_W = CHART_W;
        this.CHART_H = CHART_H;

        this.state = useState({ loading: true, data: null });

        onWillStart(async () => {
            this.state.data = await this.orm.call("itsm.ticket", "get_villa_nova_analytics_dashboard", []);
            this.state.loading = false;
        });
    }

    get maxTrendValue() {
        const trend = this.state.data.trend;
        return Math.max(1, ...trend.flatMap((d) => [d.created, d.resolved]));
    }

    get trendLines() {
        const trend = this.state.data.trend;
        const max = this.maxTrendValue;
        const stepX = (CHART_W - CHART_PAD * 2) / (trend.length - 1);
        const toY = (v) => CHART_H - CHART_PAD - (v / max) * (CHART_H - CHART_PAD * 2);
        const point = (d, i, key) => `${(CHART_PAD + i * stepX).toFixed(1)},${toY(d[key]).toFixed(1)}`;
        return {
            created: trend.map((d, i) => point(d, i, "created")).join(" "),
            resolved: trend.map((d, i) => point(d, i, "resolved")).join(" "),
        };
    }

    get trendFirstLastLabels() {
        const trend = this.state.data.trend;
        return { first: trend[0].label, last: trend[trend.length - 1].label };
    }

    get maxCategoryCount() {
        const categories = this.state.data.top_categories;
        return categories.length ? Math.max(...categories.map((c) => c.count)) : 1;
    }

    get maxResolutionHours() {
        return Math.max(1, ...Object.values(this.state.data.resolution_by_priority));
    }

    barWidthPct(value, max) {
        return value ? Math.max(3, Math.round((value / max) * 100)) : 0;
    }

    get csatTotal() {
        const csat = this.state.data.csat;
        return csat.great + csat.okay + csat.bad;
    }

    csatPct(value) {
        return this.csatTotal ? Math.round((value / this.csatTotal) * 100) : 0;
    }

    openTicketsByCategory(categoryName) {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: categoryName,
            res_model: "itsm.ticket",
            view_mode: "list,form",
            views: [[false, "list"], [false, "form"]],
            domain: [["category_id.name", "=", categoryName]],
        });
    }

    openChanges() {
        this.actionService.doAction("villa_nova_change.itsm_change_action");
    }

    openEquipment() {
        this.actionService.doAction("villa_nova_itam.itam_equipment_action");
    }

    openOverAllocatedLicenses() {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "Licences en sur-allocation",
            res_model: "itam.software.license",
            view_mode: "list,form",
            views: [[false, "list"], [false, "form"]],
            domain: [["is_over_allocated", "=", true]],
        });
    }
}

registry.category("actions").add("villa_nova_analytics.dashboard", VillaNovaAnalyticsDashboard);
