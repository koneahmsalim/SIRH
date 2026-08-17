import { reactive } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";

// Etat partage entre le rail d'icones (VillaNovaSidebar) et le panneau de
// sections (VillaNovaSectionPanel) - deux composants montes independamment
// via main_components (cf. sidebar.js) qui doivent malgre tout rester
// synchronises (ex. replier le panneau doit aussi mettre a jour le decalage
// de .o_web_client calcule par le rail). Chaque composant fait
// useState(shellState) sur cet objet : les proxies reactifs crees par
// useState() partagent la meme cible sous-jacente, donc une mutation via
// l'un notifie aussi l'autre - MAIS seulement si la mutation passe par un
// proxy reactive() (piege rencontre : muter l'objet brut directement,
// meme si des composants l'observent via useState, ne notifie personne -
// useState() sur chaque composant cree son propre proxy independant sans
// jamais toucher l'objet original). D'ou reactive() ici, au niveau module.
const PANEL_COLLAPSED_KEY = "vn_panel_collapsed";

export const shellState = reactive({
    panelCollapsed: browser.localStorage.getItem(PANEL_COLLAPSED_KEY) === "1",
});

export function togglePanelCollapsed() {
    shellState.panelCollapsed = !shellState.panelCollapsed;
    browser.localStorage.setItem(PANEL_COLLAPSED_KEY, shellState.panelCollapsed ? "1" : "0");
}
