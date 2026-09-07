// Package actions execute les commandes PREDEFINIES demandees depuis le
// SIRH - jamais de code arbitraire recu du serveur et execute tel quel.
// Execute() est un aiguillage ferme sur un catalogue fixe de command_type
// (miroir exact du catalogue cote serveur, voir
// villa_nova_endpoint/models/remote_command.py) : toute valeur hors de ce
// catalogue est rejetee ici, cote agent, en plus du controle deja fait cote
// serveur - defense en profondeur plutot que de faire confiance au seul
// controle serveur.
package actions

import "fmt"

// Params porte les arguments annexes d'une commande - regroupes dans un
// struct plutot que des paires de chaines positionnelles au fil des ajouts
// de type de commande (Phase 4 : parametre simple ; Phase 7 : contenu de
// script + empreinte).
type Params struct {
	Parameters    string
	ScriptContent string
	ScriptHash    string
}

func Execute(commandType string, p Params) (output string, err error) {
	switch commandType {
	case "restart":
		return Restart(p.Parameters)
	case "shutdown":
		return Shutdown(p.Parameters)
	case "logoff":
		return Logoff()
	case "lock":
		return Lock()
	case "notify_user":
		return NotifyUser(p.Parameters)
	case "service_status":
		return ServiceStatus(p.Parameters)
	case "service_restart":
		return ServiceRestart(p.Parameters)
	case "collect_logs":
		return CollectLogs()
	case "run_script":
		return RunScript(p.ScriptContent, p.ScriptHash)
	case "refresh_inventory":
		// Rien a faire ici : l'inventaire envoye dans LA REQUETE de check-in
		// qui a rapporte cette commande est deja frais (collecte juste avant
		// l'appel) - la demande est donc deja satisfaite par construction du
		// protocole, pas besoin de forcer un second cycle.
		return "Inventaire déjà actualisé lors de ce check-in.", nil
	default:
		return "", fmt.Errorf("type de commande inconnu ou non supporté par cette version de l'agent : %q", commandType)
	}
}
