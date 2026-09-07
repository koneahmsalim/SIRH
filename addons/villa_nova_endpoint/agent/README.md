# Agent Endpoint Villa Nova (RMM)

Agent Windows en Go, connexion sortante uniquement. Remonte l'inventaire complet du poste (matériel, logiciels, réseau, sécurité) au SIRH Villa Nova via `/endpoint/agent/enroll` puis `/endpoint/agent/checkin` (voir `addons/villa_nova_endpoint/controllers/agent.py`).

## Compilation (cross-compilation depuis Linux/macOS/CI, pas de toolchain Go nécessaire en local)

```bash
docker run --rm -v "$(pwd)/addons/villa_nova_endpoint/agent:/agent" -w /agent \
  -e GOOS=windows -e GOARCH=amd64 -e CGO_ENABLED=0 \
  golang:1.22 sh -c "go mod tidy && go build -ldflags '-X main.AgentVersion=0.1.0' -o villa-nova-endpoint-agent.exe ."
```

Produit `villa-nova-endpoint-agent.exe`, binaire statique, aucune dépendance runtime à installer sur le poste cible.

## Déploiement

1. **Générer une clé d'enrôlement** dans Odoo : *Actifs > Configuration > Clés d'enrôlement d'agents* → *Créer* → *Générer un jeton*. Copier le jeton affiché (format `<id>.<secret>`) - il n'est plus jamais réaffiché.
2. **Enrôler le poste** (une fois, avec des droits administrateur locaux) :
   ```
   villa-nova-endpoint-agent.exe -enroll -server https://sirh.infinity-africa.com -key "<jeton>"
   ```
   Crée `%ProgramData%\VillaNovaEndpointAgent\config.json` (secret d'agent chiffré DPAPI, portée machine).
3. **Installer le service Windows** (démarrage automatique, tourne en LocalSystem) :
   ```
   villa-nova-endpoint-agent.exe -install-service
   ```
4. Le service fait un check-in toutes les 15 minutes par défaut (configurable côté serveur via `checkin_interval_seconds` dans la réponse d'API).

Pour un déploiement de masse (GPO/MSI), la même clé d'enrôlement peut être intégrée dans le script de déploiement et réutilisée par tous les postes ciblés - chaque poste reçoit ensuite sa propre identité/secret unique à l'enrôlement (jamais partagé entre postes).

## Débogage local

```
villa-nova-endpoint-agent.exe -print-inventory   REM affiche l'inventaire JSON collecté, sans contacter le serveur
villa-nova-endpoint-agent.exe -run               REM boucle de check-in au premier plan (après -enroll), Ctrl+C pour arrêter
villa-nova-endpoint-agent.exe -uninstall-service  REM retire le service Windows
```

## Limites connues de cette phase (Phase 2 - Agent MVP)

- **Pas d'exécution de commandes à distance.** Le contrat de check-in réserve un champ `commands` (toujours vide dans cette phase) pour une future phase "Actions à distance" du projet, mais aucune exécution n'est implémentée ici - contrainte explicite du projet contre l'exécution arbitraire non contrôlée.
- **Détection des écrans (`monitor_count`)** dépend de la classe WMI `WmiMonitorID` (`root\wmi`), connue pour être peu fiable selon le pilote graphique installé - peut renvoyer 0 sur une machine réelle qui a bien un écran branché. À vérifier en priorité lors du premier test sur un poste Windows réel.
- **Classification SSD/HDD** des disques est une heuristique par mots-clés (WMI n'expose pas cette information de façon fiable) - `media_type` peut rester `unknown` sur du matériel dont le modèle ne contient aucun indice.
- **Windows uniquement.** Linux/macOS sont hors périmètre de cette phase (le brief projet les prévoit "plus tard").
- **Non testé sur une vraie machine Windows** depuis cet environnement de développement (pas de poste Windows disponible ici) - seule la compilation croisée a été vérifiée (`go build`/`go vet` réussissent pour GOOS=windows). Un premier test réel sur un poste Windows (idéalement une VM jetable) est nécessaire avant tout déploiement, en particulier pour confirmer le comportement du service Windows, DPAPI, et la détection des écrans/de la batterie.
