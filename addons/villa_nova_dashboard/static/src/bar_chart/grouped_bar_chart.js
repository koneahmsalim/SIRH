import { Component } from "@odoo/owl";

/**
 * Variante a 2 series (ex. embauches vs departs par mois) du graphique en
 * barres maison - meme logique "aucune dependance externe" que VnBarChart.
 */
export class VnGroupedBarChart extends Component {
    static template = "villa_nova_dashboard.GroupedBarChart";
    static props = {
        labels: Array, // ["Jan", "Fev", ...]
        series: Array, // [{name, color, values: [n, n, ...]}]
    };

    get maxValue() {
        const all = this.props.series.flatMap((s) => s.values);
        return Math.max(1, ...all);
    }

    heightPercent(value) {
        return Math.round(((value || 0) / this.maxValue) * 100);
    }
}
