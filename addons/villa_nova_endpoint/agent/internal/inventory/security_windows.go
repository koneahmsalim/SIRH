package inventory

import (
	"strconv"
	"time"

	"github.com/yusufpapurcu/wmi"
)

// win32AntiVirusProduct vit dans le namespace root/SecurityCenter2, pas
// root/cimv2 - expose par Windows Security Center pour tout AV/EDR tiers
// ET Windows Defender lui-meme (un seul agent, jamais besoin de cas
// particulier "si c'est Defender").
type win32AntiVirusProduct struct {
	DisplayName  string
	ProductState uint32
}

// win32QuickFixEngineering (root/cimv2, natif) : liste les correctifs
// installes - on prend la date d'installation la plus recente comme proxy
// de "mises a jour a jour", faute d'API simple sans COM pour interroger
// Windows Update directement depuis Go.
type win32QuickFixEngineering struct {
	InstalledOn string
}

// win32EncryptableVolume (namespace root/cimv2/security/MicrosoftVolumeEncryption)
// expose l'etat BitLocker par volume - on ne regarde que C: (volume systeme),
// le seul pertinent pour une politique de conformite de poste.
type win32EncryptableVolume struct {
	DriveLetter      string
	ProtectionStatus uint32
}

const patchOverdueDays = 90
const patchPendingDays = 30

func CollectSecurity() Security {
	sec := Security{
		AVStatus:    collectAVStatus(),
		PatchStatus: collectPatchStatus(),
	}
	sec.EncryptionEnabled = collectEncryptionEnabled()
	return sec
}

func collectAVStatus() string {
	var products []win32AntiVirusProduct
	if err := wmi.QueryNamespace(
		"SELECT DisplayName, ProductState FROM AntiVirusProduct", &products, `root\SecurityCenter2`,
	); err != nil || len(products) == 0 {
		return "unknown"
	}
	for _, p := range products {
		// ProductState est un bitmask historique (non documenté
		// officiellement mais stable depuis Vista) : l'octet du milieu
		// indique l'activation temps reel. 0x10 = activé.
		enabled := (p.ProductState>>8)&0xFF&0x10 != 0
		if enabled {
			return "protected"
		}
	}
	return "at_risk"
}

func collectPatchStatus() string {
	var hotfixes []win32QuickFixEngineering
	if err := wmi.Query("SELECT InstalledOn FROM Win32_QuickFixEngineering", &hotfixes); err != nil || len(hotfixes) == 0 {
		return "unknown"
	}
	var latest time.Time
	for _, h := range hotfixes {
		t, err := parseWMIDate(h.InstalledOn)
		if err == nil && t.After(latest) {
			latest = t
		}
	}
	if latest.IsZero() {
		return "unknown"
	}
	daysSince := time.Since(latest).Hours() / 24
	switch {
	case daysSince <= patchPendingDays:
		return "up_to_date"
	case daysSince <= patchOverdueDays:
		return "pending"
	default:
		return "overdue"
	}
}

func collectEncryptionEnabled() bool {
	var volumes []win32EncryptableVolume
	if err := wmi.QueryNamespace(
		"SELECT DriveLetter, ProtectionStatus FROM Win32_EncryptableVolume WHERE DriveLetter = 'C:'",
		&volumes, `root\cimv2\security\MicrosoftVolumeEncryption`,
	); err != nil || len(volumes) == 0 {
		return false
	}
	return volumes[0].ProtectionStatus == 1
}

// parseWMIDate accepte les deux formats releves en pratique pour
// InstalledOn : "1/15/2025" (le plus courant, locale-dependant) ou le format
// WMI natif "20250115000000.000000+000".
func parseWMIDate(raw string) (time.Time, error) {
	if t, err := time.Parse("1/2/2006", raw); err == nil {
		return t, nil
	}
	if len(raw) >= 8 {
		if _, err := strconv.Atoi(raw[0:8]); err == nil {
			if t, err := time.Parse("20060102", raw[0:8]); err == nil {
				return t, nil
			}
		}
	}
	return time.Time{}, &time.ParseError{}
}
