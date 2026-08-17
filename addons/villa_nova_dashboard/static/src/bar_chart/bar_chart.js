import { Component } from "@odoo/owl";

/**
 * Petit graphique en barres en SVG pur (aucune dependance externe - voir
 * le probleme de Chart.js charge depuis un CDN sur hrms_dashboard, cassé
 * hors ligne, que ce module remplace).
 */
export class VnBarChart extends Component {
    static template = "villa_nova_dashboard.BarChart";
    static props = {
        data: Array, // [{label, value}]
        orientation: { type: String, optional: true }, // "horizontal" | "vertical"
        color: { type: String, optional: true },
        emptyLabel: { type: String, optional: true },
    };
    static defaultProps = {
        orientation: "vertical",
        color: "var(--vn-crimson)",
    };

    get maxValue() {
        return Math.max(1, ...this.props.data.map((d) => d.value || 0));
    }

    widthPercent(value) {
        return Math.round(((value || 0) / this.maxValue) * 100);
    }
}
