import { _t } from "@web/core/l10n/translation";
import { browser } from "@web/core/browser/browser";
import { registry } from "@web/core/registry";

// Odoo a deja un mecanisme natif pour ca (bus/assets_watchdog_service.js),
// mais il ne notifie que si `release.version` (la version d'Odoo) change -
// jamais sur nos propres deploiements des modules villa_nova_* (meme
// version Odoo a chaque fois). Or le serveur emet DEJA l'evenement bus
// "bundle_changed" a chaque recompilation de web.assets_web (voir
// assetsbundle.py, TRACKED_BUNDLES) - precisement le bundle dont l'absence
// de mise a jour cote client a cause l'erreur "Cannot find key ... in the
// actions registry" en session de dev. On reutilise ce meme signal, sans la
// garde de version : ici, tout bundle_changed pendant une session active
// signifie reellement "il faut recharger la page".
export const villaNovaReloadWatchdogService = {
    dependencies: ["bus_service", "notification"],

    start(env, { bus_service, notification }) {
        let notified = false;

        bus_service.subscribe("bundle_changed", () => {
            if (notified) {
                return;
            }
            notified = true;
            // Delai aleatoire (comme le mecanisme natif) pour ne pas
            // recharger tout le monde en meme temps si un deploiement
            // touche plusieurs personnes connectees simultanement.
            browser.setTimeout(() => {
                notification.add(
                    _t("Une nouvelle version de l'application est disponible."),
                    {
                        title: _t("Mise à jour"),
                        type: "warning",
                        sticky: true,
                        buttons: [
                            {
                                name: _t("Recharger"),
                                primary: true,
                                onClick: () => browser.location.reload(),
                            },
                        ],
                    }
                );
            }, 10000 + Math.floor(Math.random() * 20) * 1000);
        });
        bus_service.start();
    },
};

registry.category("services").add("villaNovaReloadWatchdog", villaNovaReloadWatchdogService);
