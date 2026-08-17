import { Component, useState, onWillDestroy } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { shellState, togglePanelCollapsed } from "./shell_state";

function getMenuItemHref(payload) {
    return `/odoo/${payload.actionPath || "action-" + payload.actionID}`;
}

// Panneau secondaire : categories de l'app active en accordeon (un seul
// groupe ouvert a la fois, les autres se replient). Ne se rend que si
// l'app active a au moins une section - certaines apps (Dashboard,
// Reminders, To-do...) sont des ecrans uniques, pas besoin de panneau.
export class VillaNovaSectionPanel extends Component {
    static template = "villa_nova_shell.SectionPanel";
    static props = {};

    setup() {
        this.menuService = useService("menu");
        this.actionService = useService("action");
        this.ui = useState(useService("ui"));
        this.shellState = useState(shellState);
        this.togglePanelCollapsed = togglePanelCollapsed;
        this.getMenuItemHref = getMenuItemHref;

        this.state = useState({
            currentActionId: this.actionService.currentController?.action?.id,
            expandedGroupId: null,
        });

        const onAppChanged = () => {
            this.autoExpandActiveGroup();
            this.render();
        };
        const onActionUpdated = () => {
            this.state.currentActionId = this.actionService.currentController?.action?.id;
            this.autoExpandActiveGroup();
        };
        this.env.bus.addEventListener("MENUS:APP-CHANGED", onAppChanged);
        this.env.bus.addEventListener("ACTION_MANAGER:UI-UPDATED", onActionUpdated);
        onWillDestroy(() => {
            this.env.bus.removeEventListener("MENUS:APP-CHANGED", onAppChanged);
            this.env.bus.removeEventListener("ACTION_MANAGER:UI-UPDATED", onActionUpdated);
        });

        this.autoExpandActiveGroup();
    }

    get currentApp() {
        return this.menuService.getCurrentApp();
    }

    get sections() {
        const app = this.currentApp;
        return (app && this.menuService.getMenuAsTree(app.id).childrenTree) || [];
    }

    containsAction(node, actionId) {
        if (node.actionID === actionId) {
            return true;
        }
        return (node.childrenTree || []).some((child) => this.containsAction(child, actionId));
    }

    autoExpandActiveGroup() {
        const actionId = this.actionService.currentController?.action?.id;
        if (!actionId) {
            return;
        }
        for (const top of this.sections) {
            if (this.containsAction(top, actionId)) {
                this.state.expandedGroupId = top.id;
                return;
            }
        }
    }

    isGroupExpanded(section) {
        return this.state.expandedGroupId === section.id;
    }

    toggleGroup(section) {
        this.state.expandedGroupId = this.isGroupExpanded(section) ? null : section.id;
    }

    isActiveLeaf(section) {
        return !!section.actionID && section.actionID === this.state.currentActionId;
    }

    onLeafClick(section) {
        this.menuService.selectMenu(section);
    }
}

registry.category("main_components").add("villa_nova_shell.SectionPanel", {
    Component: VillaNovaSectionPanel,
});
