package actions

import (
	"fmt"
	"strings"
	"time"

	"github.com/yusufpapurcu/wmi"
)

type win32NTLogEvent struct {
	LogFile        string
	SourceName     string
	EventType      uint16
	TimeGenerated  string
	Message        string
}

const logCollectionHours = 24
const logCollectionMaxEntries = 100

var eventTypeNames = map[uint16]string{1: "Erreur", 2: "Avertissement"}

// CollectLogs remonte les evenements ERREUR/AVERTISSEMENT recents des
// journaux Application et Systeme (pas Information - trop volumineux et peu
// utile pour un diagnostic ponctuel) via WMI, plutot que wevtutil.exe (sortie
// moins structuree) - meme bibliotheque WMI que le reste de l'agent.
func CollectLogs() (string, error) {
	cutoff := time.Now().Add(-logCollectionHours * time.Hour).UTC().Format("20060102150405.000000") + "+000"
	query := fmt.Sprintf(
		"SELECT LogFile, SourceName, EventType, TimeGenerated, Message FROM Win32_NTLogEvent "+
			"WHERE (LogFile='Application' OR LogFile='System') AND (EventType=1 OR EventType=2) "+
			"AND TimeGenerated >= '%s'", cutoff,
	)
	var events []win32NTLogEvent
	if err := wmi.Query(query, &events); err != nil {
		return "", fmt.Errorf("lecture des journaux d'événements : %w", err)
	}

	if len(events) == 0 {
		return fmt.Sprintf("Aucune erreur/avertissement dans les journaux Application/Système "+
			"des dernières %dh.", logCollectionHours), nil
	}
	if len(events) > logCollectionMaxEntries {
		events = events[:logCollectionMaxEntries]
	}

	var sb strings.Builder
	fmt.Fprintf(&sb, "%d événement(s) Erreur/Avertissement sur les dernières %dh "+
		"(Application/Système, limité à %d) :\n\n", len(events), logCollectionHours, logCollectionMaxEntries)
	for _, e := range events {
		typeName := eventTypeNames[e.EventType]
		if typeName == "" {
			typeName = fmt.Sprintf("Type %d", e.EventType)
		}
		message := strings.TrimSpace(e.Message)
		if len(message) > 300 {
			message = message[:300] + "…"
		}
		fmt.Fprintf(&sb, "[%s] %s / %s (%s)\n%s\n\n", e.TimeGenerated, e.LogFile, e.SourceName, typeName, message)
	}
	return sb.String(), nil
}
