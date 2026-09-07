// Package svc intègre l'agent comme un vrai service Windows (démarrage
// automatique, survit à la fermeture de session, redémarrage géré par le
// Service Control Manager) via golang.org/x/sys/windows/svc - bibliothèque
// officielle de l'écosystème Go pour Windows, pas une dépendance tierce
// supplémentaire.
package svc

import (
	"fmt"
	"os"
	"time"

	wsvc "golang.org/x/sys/windows/svc"
	"golang.org/x/sys/windows/svc/eventlog"
	"golang.org/x/sys/windows/svc/mgr"
)

const ServiceName = "VillaNovaEndpointAgent"
const ServiceDisplayName = "Villa Nova - Agent Endpoint (RMM)"
const ServiceDescription = "Remonte l'inventaire matériel/logiciel/réseau du poste et exécute les actions approuvées demandées depuis le SIRH Villa Nova."

type RunFunc func(stop <-chan struct{})

type handler struct {
	run RunFunc
}

func (h *handler) Execute(args []string, r <-chan wsvc.ChangeRequest, s chan<- wsvc.Status) (bool, uint32) {
	s <- wsvc.Status{State: wsvc.StartPending}
	stop := make(chan struct{})
	done := make(chan struct{})
	go func() {
		h.run(stop)
		close(done)
	}()
	s <- wsvc.Status{State: wsvc.Running, Accepts: wsvc.AcceptStop | wsvc.AcceptShutdown}

	for {
		select {
		case req := <-r:
			switch req.Cmd {
			case wsvc.Interrogate:
				s <- req.CurrentStatus
			case wsvc.Stop, wsvc.Shutdown:
				s <- wsvc.Status{State: wsvc.StopPending}
				close(stop)
				<-done
				s <- wsvc.Status{State: wsvc.Stopped}
				return false, 0
			}
		case <-done:
			s <- wsvc.Status{State: wsvc.Stopped}
			return false, 0
		}
	}
}

// RunAsService bloque jusqu'à l'arrêt du service - à appeler depuis main()
// quand le processus est lancé PAR le Service Control Manager (détecté via
// IsRunningAsService).
func RunAsService(run RunFunc) error {
	elog, err := eventlog.Open(ServiceName)
	if err == nil {
		defer elog.Close()
		elog.Info(1, "Villa Nova Endpoint Agent : démarrage du service")
	}
	return wsvc.Run(ServiceName, &handler{run: run})
}

func IsRunningAsService() bool {
	isService, err := wsvc.IsWindowsService()
	return err == nil && isService
}

// Install enregistre le service (démarrage automatique) et sa source de
// journal d'événements - à appeler une fois via `agent.exe -install-service`
// (typiquement depuis le script post-installation du MSI/GPO).
func Install() error {
	exePath, err := os.Executable()
	if err != nil {
		return fmt.Errorf("résolution du chemin de l'exécutable : %w", err)
	}

	m, err := mgr.Connect()
	if err != nil {
		return fmt.Errorf("connexion au Service Control Manager : %w", err)
	}
	defer m.Disconnect()

	if existing, err := m.OpenService(ServiceName); err == nil {
		existing.Close()
		return fmt.Errorf("le service %s existe déjà - désinstallez-le d'abord (-uninstall-service)", ServiceName)
	}

	s, err := m.CreateService(ServiceName, exePath, mgr.Config{
		DisplayName: ServiceDisplayName,
		Description: ServiceDescription,
		StartType:   mgr.StartAutomatic,
	})
	if err != nil {
		return fmt.Errorf("création du service : %w", err)
	}
	defer s.Close()

	if err := eventlog.InstallAsEventCreate(ServiceName, eventlog.Error|eventlog.Warning|eventlog.Info); err != nil {
		// Non-bloquant : l'agent fonctionne sans source de journal
		// d'événements dédiée, juste avec des logs moins bien intégrés à
		// l'Observateur d'événements Windows.
		fmt.Printf("avertissement : source de journal d'événements non installée : %v\n", err)
	}

	if err := s.Start(); err != nil {
		return fmt.Errorf("service créé mais échec du démarrage : %w", err)
	}
	return nil
}

func Uninstall() error {
	m, err := mgr.Connect()
	if err != nil {
		return fmt.Errorf("connexion au Service Control Manager : %w", err)
	}
	defer m.Disconnect()

	s, err := m.OpenService(ServiceName)
	if err != nil {
		return fmt.Errorf("service introuvable : %w", err)
	}
	defer s.Close()

	status, err := s.Query()
	if err == nil && status.State != wsvc.Stopped {
		if _, err := s.Control(wsvc.Stop); err == nil {
			for i := 0; i < 30; i++ {
				status, err := s.Query()
				if err != nil || status.State == wsvc.Stopped {
					break
				}
				time.Sleep(time.Second)
			}
		}
	}

	if err := s.Delete(); err != nil {
		return fmt.Errorf("suppression du service : %w", err)
	}
	_ = eventlog.Remove(ServiceName)
	return nil
}
