/* @odoo-module */

import { onWillDestroy } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { ActivityMenu } from "@hr_attendance/components/attendance_menu/attendance_menu";

// Le widget natif ne relit hr.attendance qu'au chargement de la page ou juste
// apres un clic de l'utilisateur - un pointage badgeuse synchronise en tache
// de fond (cron) ne se reflete donc jamais sans rechargement manuel. On
// rafraichit ici en tache de fond, au meme rythme que la synchro badgeuse.
const VILLA_NOVA_REFRESH_INTERVAL_MS = 3 * 60 * 1000;

patch(ActivityMenu.prototype, {
    setup() {
        super.setup();
        const intervalId = setInterval(() => this.searchReadEmployee(), VILLA_NOVA_REFRESH_INTERVAL_MS);
        onWillDestroy(() => clearInterval(intervalId));
    },
});
