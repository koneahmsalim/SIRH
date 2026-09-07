// Villa Nova - Agent Endpoint (RMM)
//
// Agent Windows en connexion sortante uniquement : il interroge le serveur
// SIRH Villa Nova (jamais l'inverse), s'enrôle une fois avec une clé
// organisationnelle puis fait un check-in périodique en s'authentifiant
// avec une identité qui lui est propre (jamais partagée avec les autres
// postes). Voir addons/villa_nova_endpoint/agent/README.md pour le
// déploiement complet et addons/villa_nova_endpoint/controllers/agent.py
// côté serveur pour le contrat d'API exact.
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"os"
	"time"

	"github.com/infinity-africa/villa-nova-endpoint-agent/internal/client"
	"github.com/infinity-africa/villa-nova-endpoint-agent/internal/config"
	"github.com/infinity-africa/villa-nova-endpoint-agent/internal/inventory"
	"github.com/infinity-africa/villa-nova-endpoint-agent/internal/svc"
)

// AgentVersion est substituée au build via -ldflags "-X main.AgentVersion=...";
// une valeur de repli explicite évite un champ vide silencieux côté serveur
// si un binaire est un jour compilé sans ce paramètre.
var AgentVersion = "0.1.0-dev"

func main() {
	enrollCmd := flag.Bool("enroll", false, "Enrôle cet agent auprès du serveur (nécessite -server et -key)")
	serverURL := flag.String("server", "", "URL du serveur SIRH, ex. https://sirh.infinity-africa.com")
	enrollmentKey := flag.String("key", "", "Jeton d'enrôlement complet (\"<public_id>.<secret>\")")
	installService := flag.Bool("install-service", false, "Installe l'agent comme service Windows (démarrage automatique)")
	uninstallService := flag.Bool("uninstall-service", false, "Désinstalle le service Windows")
	runForeground := flag.Bool("run", false, "Exécute la boucle de check-in au premier plan (débogage - pas de service)")
	printInventory := flag.Bool("print-inventory", false, "Affiche l'inventaire collecté en JSON et quitte, sans contacter le serveur")
	flag.Parse()

	switch {
	case *printInventory:
		cmdPrintInventory()
	case *enrollCmd:
		cmdEnroll(*serverURL, *enrollmentKey)
	case *installService:
		cmdInstallService()
	case *uninstallService:
		cmdUninstallService()
	case *runForeground:
		runCheckinLoop(nil)
	case svc.IsRunningAsService():
		if err := svc.RunAsService(runCheckinLoop); err != nil {
			log.Fatalf("échec du service : %v", err)
		}
	default:
		flag.Usage()
		fmt.Println("\nAucune action précisée. Utilisez -enroll pour un premier enrôlement,")
		fmt.Println("puis -install-service pour déployer l'agent en service Windows.")
		os.Exit(2)
	}
}

func cmdPrintInventory() {
	payload := inventory.Collect(AgentVersion)
	printJSON(payload)
}

func cmdEnroll(serverURL, enrollmentKey string) {
	if serverURL == "" || enrollmentKey == "" {
		log.Fatal("-server et -key sont obligatoires pour -enroll")
	}
	payload := inventory.Collect(AgentVersion)
	c := client.New(serverURL)
	resp, err := c.Enroll(enrollmentKey, payload)
	if err != nil {
		log.Fatalf("échec de l'enrôlement : %v", err)
	}

	err = config.Save(&config.Config{
		ServerURL:              serverURL,
		AgentID:                resp.AgentID,
		AgentSecret:            resp.AgentSecret,
		CheckinIntervalSeconds: resp.CheckinIntervalSeconds,
	})
	if err != nil {
		log.Fatalf("enrôlement réussi côté serveur (agent %s) mais échec de l'écriture de la configuration locale : %v", resp.AgentID, err)
	}

	fmt.Printf("Enrôlement réussi. Identifiant d'agent : %s (actif Odoo #%d)\n", resp.AgentID, resp.EquipmentID)
	fmt.Println("Configuration enregistrée (secret chiffré DPAPI). Vous pouvez maintenant lancer -install-service.")
}

func cmdInstallService() {
	if !config.IsEnrolled() {
		log.Fatal("agent non enrôlé - lancez d'abord -enroll -server <url> -key <jeton>")
	}
	if err := svc.Install(); err != nil {
		log.Fatalf("échec de l'installation du service : %v", err)
	}
	fmt.Println("Service installé et démarré.")
}

func cmdUninstallService() {
	if err := svc.Uninstall(); err != nil {
		log.Fatalf("échec de la désinstallation du service : %v", err)
	}
	fmt.Println("Service désinstallé.")
}

// runCheckinLoop est le corps d'exécution partagé entre le mode service
// Windows (stop signalé par le canal fermé par svc.handler) et le mode
// -run au premier plan (stop == nil, boucle jusqu'à Ctrl+C/kill process).
func runCheckinLoop(stop <-chan struct{}) {
	cfg, err := config.Load()
	if err != nil {
		log.Fatalf("agent non enrôlé ou configuration illisible (%v) - lancez -enroll d'abord", err)
	}
	c := client.New(cfg.ServerURL)
	interval := time.Duration(cfg.CheckinIntervalSeconds) * time.Second

	doCheckin := func() {
		payload := inventory.Collect(AgentVersion)
		resp, err := c.Checkin(cfg.AgentID, cfg.AgentSecret, payload)
		if err != nil {
			log.Printf("check-in échoué : %v", err)
			return
		}
		if resp.CheckinIntervalSeconds > 0 {
			interval = time.Duration(resp.CheckinIntervalSeconds) * time.Second
		}
		log.Printf("check-in ok (prochain dans %s)", interval)
	}

	// stop == nil en mode -run au premier plan : un canal nil bloque
	// indéfiniment dans un select (jamais prêt), ce qui est exactement le
	// comportement voulu (la boucle ne s'arrête alors que sur Ctrl+C/kill).
	doCheckin()
	ticker := time.NewTicker(interval)
	defer ticker.Stop()
	for {
		select {
		case <-ticker.C:
			doCheckin()
		case <-stop:
			return
		}
	}
}

func printJSON(v interface{}) {
	enc := json.NewEncoder(os.Stdout)
	enc.SetIndent("", "  ")
	if err := enc.Encode(v); err != nil {
		log.Fatalf("sérialisation JSON : %v", err)
	}
}
