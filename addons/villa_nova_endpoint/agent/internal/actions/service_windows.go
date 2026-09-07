package actions

import (
	"fmt"
	"time"

	"golang.org/x/sys/windows/svc"
	"golang.org/x/sys/windows/svc/mgr"
)

var serviceStateNames = map[svc.State]string{
	svc.Stopped:         "arrêté",
	svc.StartPending:    "démarrage en cours",
	svc.StopPending:     "arrêt en cours",
	svc.Running:         "en cours d'exécution",
	svc.ContinuePending: "reprise en cours",
	svc.PausePending:    "pause en cours",
	svc.Paused:          "en pause",
}

// ServiceStatus interroge l'etat d'un service Windows NOMME (parametre
// fourni par l'operateur, jamais du code arbitraire) via le Service Control
// Manager natif - lecture seule, aucun risque.
func ServiceStatus(serviceName string) (string, error) {
	if serviceName == "" {
		return "", fmt.Errorf("nom de service manquant")
	}
	m, err := mgr.Connect()
	if err != nil {
		return "", fmt.Errorf("connexion au Service Control Manager : %w", err)
	}
	defer m.Disconnect()

	s, err := m.OpenService(serviceName)
	if err != nil {
		return "", fmt.Errorf("service %q introuvable : %w", serviceName, err)
	}
	defer s.Close()

	status, err := s.Query()
	if err != nil {
		return "", fmt.Errorf("interrogation du service %q : %w", serviceName, err)
	}
	name := serviceStateNames[status.State]
	if name == "" {
		name = fmt.Sprintf("état inconnu (%d)", status.State)
	}
	return fmt.Sprintf("Service %q : %s.", serviceName, name), nil
}

// ServiceRestart arrete puis redemarre un service Windows NOMME - action
// sensible (interrompt un service potentiellement en production), passe par
// l'approbation cote serveur avant d'atteindre l'agent (voir
// itsm.remote.command : SENSITIVE_COMMANDS).
func ServiceRestart(serviceName string) (string, error) {
	if serviceName == "" {
		return "", fmt.Errorf("nom de service manquant")
	}
	m, err := mgr.Connect()
	if err != nil {
		return "", fmt.Errorf("connexion au Service Control Manager : %w", err)
	}
	defer m.Disconnect()

	s, err := m.OpenService(serviceName)
	if err != nil {
		return "", fmt.Errorf("service %q introuvable : %w", serviceName, err)
	}
	defer s.Close()

	status, err := s.Query()
	if err != nil {
		return "", fmt.Errorf("interrogation du service %q : %w", serviceName, err)
	}

	if status.State != svc.Stopped {
		if _, err := s.Control(svc.Stop); err != nil {
			return "", fmt.Errorf("arrêt du service %q : %w", serviceName, err)
		}
		if err := waitForState(s, svc.Stopped, 30*time.Second); err != nil {
			return "", fmt.Errorf("service %q non arrêté à temps : %w", serviceName, err)
		}
	}

	if err := s.Start(); err != nil {
		return "", fmt.Errorf("démarrage du service %q : %w", serviceName, err)
	}
	if err := waitForState(s, svc.Running, 30*time.Second); err != nil {
		return "", fmt.Errorf("service %q non démarré à temps : %w", serviceName, err)
	}
	return fmt.Sprintf("Service %q redémarré avec succès.", serviceName), nil
}

func waitForState(s *mgr.Service, want svc.State, timeout time.Duration) error {
	deadline := time.Now().Add(timeout)
	for time.Now().Before(deadline) {
		status, err := s.Query()
		if err != nil {
			return err
		}
		if status.State == want {
			return nil
		}
		time.Sleep(500 * time.Millisecond)
	}
	return fmt.Errorf("délai dépassé")
}
