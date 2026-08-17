import { Component, useState, useEffect, onWillDestroy } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { browser } from "@web/core/browser/browser";
import { UserMenu } from "@web/webclient/user_menu/user_menu";

const COLLAPSED_STORAGE_KEY = "vn_sidebar_collapsed";
const BODY_CLASS = "vn-has-sidebar";
const BODY_COLLAPSED_CLASS = "vn-sidebar-collapsed";

// Reprend le meme format d'URL que web.NavBar (voir getMenuItemHref dans
// navbar.js) pour que le clic milieu / ctrl-clic (ouverture dans un nouvel
// onglet) continue de fonctionner sur les entrees de la sidebar.
function getMenuItemHref(payload) {
    return `/odoo/${payload.actionPath || "action-" + payload.actionID}`;
}

export class VillaNovaSidebar extends Component {
    static template = "villa_nova_shell.Sidebar";
    static components = { UserMenu };
    static props = {};

    setup() {
        this.menuService = useService("menu");
        this.actionService = useService("action");
        this.commandService = useService("command");
        this.ui = useState(useService("ui"));
        this.getMenuItemHref = getMenuItemHref;

        this.state = useState({
            collapsed: browser.localStorage.getItem(COLLAPSED_STORAGE_KEY) === "1",
            currentActionId: this.actionService.currentController?.action?.id,
        });

        const onAppChanged = () => this.render();
        const onActionUpdated = () => {
            this.state.currentActionId = this.actionService.currentController?.action?.id;
        };
        this.env.bus.addEventListener("MENUS:APP-CHANGED", onAppChanged);
        this.env.bus.addEventListener("ACTION_MANAGER:UI-UPDATED", onActionUpdated);
        onWillDestroy(() => {
            this.env.bus.removeEventListener("MENUS:APP-CHANGED", onAppChanged);
            this.env.bus.removeEventListener("ACTION_MANAGER:UI-UPDATED", onActionUpdated);
            document.body.classList.remove(BODY_CLASS, BODY_COLLAPSED_CLASS);
        });

        // La sidebar est montee hors du flux (position: fixed, via
        // registry main_components - cf. bas de fichier) pour ne jamais
        // toucher aux templates/composants du coeur (WebClient/NavBar).
        // On reserve donc sa place en poussant .o_web_client via une
        // classe sur <body>, plutot que par imbrication DOM reelle. Sur
        // petit ecran, la sidebar ne se rend pas (t-if isSmall dans le
        // template) : les overlays mobiles natifs d'Odoo restent seuls
        // maitres a bord et aucun decalage ne doit s'appliquer.
        useEffect(
            (isSmall, collapsed) => {
                document.body.classList.toggle(BODY_CLASS, !isSmall);
                document.body.classList.toggle(BODY_COLLAPSED_CLASS, !isSmall && collapsed);
            },
            () => [this.ui.isSmall, this.state.collapsed]
        );
    }

    get apps() {
        return this.menuService.getApps();
    }

    get currentApp() {
        return this.menuService.getCurrentApp();
    }

    get currentAppSections() {
        const app = this.currentApp;
        return (app && this.menuService.getMenuAsTree(app.id).childrenTree) || [];
    }

    isCurrentApp(app) {
        return this.currentApp?.id === app.id;
    }

    isCurrentSection(section) {
        return !!section.actionID && section.actionID === this.state.currentActionId;
    }

    toggleCollapsed() {
        this.state.collapsed = !this.state.collapsed;
        browser.localStorage.setItem(COLLAPSED_STORAGE_KEY, this.state.collapsed ? "1" : "0");
    }

    onAppClick(app) {
        this.menuService.selectMenu(app);
    }

    onSectionClick(section) {
        this.menuService.selectMenu(section);
    }

    openSearch() {
        this.commandService.openMainPalette();
    }
}

registry.category("main_components").add("villa_nova_shell.Sidebar", {
    Component: VillaNovaSidebar,
});
