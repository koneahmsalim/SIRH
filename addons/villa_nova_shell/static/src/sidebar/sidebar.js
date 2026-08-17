import { Component, useState, useEffect, onWillDestroy } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { UserMenu } from "@web/webclient/user_menu/user_menu";
import { shellState } from "./shell_state";

const BODY_CLASS = "vn-has-sidebar";
const RAIL_WIDTH = 72;
const PANEL_WIDTH = 260;

// Reprend le meme format d'URL que web.NavBar (voir getMenuItemHref dans
// navbar.js) pour que le clic milieu / ctrl-clic (ouverture dans un nouvel
// onglet) continue de fonctionner sur les entrees de la sidebar.
function getMenuItemHref(payload) {
    return `/odoo/${payload.actionPath || "action-" + payload.actionID}`;
}

// Rail d'icones permanent (façon VSCode/Slack) : uniquement le switcher
// d'applications. Les sections de l'app active vivent dans un panneau
// separe (villa_nova_shell.SectionPanel, voir section_panel.js) plutot que
// depliees ici - c'est le coeur de la refonte de navigation (cf. commit) :
// Employes a 13 categories de premier niveau, les afficher toutes en meme
// temps dans le rail produisait exactement le "mur d'elements" a eviter.
export class VillaNovaSidebar extends Component {
    static template = "villa_nova_shell.Sidebar";
    static components = { UserMenu };
    static props = {};

    setup() {
        this.menuService = useService("menu");
        this.actionService = useService("action");
        this.commandService = useService("command");
        this.ui = useState(useService("ui"));
        this.shellState = useState(shellState);
        this.getMenuItemHref = getMenuItemHref;

        const onAppChanged = () => this.render();
        this.env.bus.addEventListener("MENUS:APP-CHANGED", onAppChanged);
        onWillDestroy(() => {
            this.env.bus.removeEventListener("MENUS:APP-CHANGED", onAppChanged);
            document.body.classList.remove(BODY_CLASS);
            document.body.style.removeProperty("--vn-shell-offset");
        });

        // Le rail (et le panneau, monte separement) sont hors du flux
        // (position: fixed, via registry main_components) pour ne jamais
        // toucher aux composants du coeur Odoo. On reserve donc leur place
        // en poussant .o_web_client via une variable CSS sur <body>,
        // recalculee ici selon : ecran mobile (aucun decalage, les
        // overlays natifs Odoo reprennent la main), app sans section
        // (rail seul) ou app avec sections (rail + panneau, sauf si
        // l'utilisateur l'a replie).
        useEffect(
            (isSmall, panelCollapsed, hasSections) => {
                if (isSmall) {
                    document.body.classList.remove(BODY_CLASS);
                    document.body.style.removeProperty("--vn-shell-offset");
                    return;
                }
                document.body.classList.add(BODY_CLASS);
                const offset = RAIL_WIDTH + (hasSections && !panelCollapsed ? PANEL_WIDTH : 0);
                document.body.style.setProperty("--vn-shell-offset", `${offset}px`);
            },
            () => [this.ui.isSmall, this.shellState.panelCollapsed, this.currentAppSectionsCount > 0]
        );
    }

    get apps() {
        return this.menuService.getApps();
    }

    get currentApp() {
        return this.menuService.getCurrentApp();
    }

    get currentAppSectionsCount() {
        const app = this.currentApp;
        return (app && this.menuService.getMenuAsTree(app.id).childrenTree.length) || 0;
    }

    isCurrentApp(app) {
        return this.currentApp?.id === app.id;
    }

    onAppClick(app) {
        this.menuService.selectMenu(app);
    }

    openSearch() {
        this.commandService.openMainPalette();
    }
}

registry.category("main_components").add("villa_nova_shell.Sidebar", {
    Component: VillaNovaSidebar,
});
