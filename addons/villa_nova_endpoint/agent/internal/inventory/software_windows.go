package inventory

import (
	"strconv"
	"strings"

	"golang.org/x/sys/windows/registry"
)

// uninstallKeys : 64 bits natif + WOW6432Node (applications 32 bits sur un
// OS 64 bits) - deliberement PAS Win32_Product (WMI), connu pour declencher
// une reparation MSI en effet de bord au moment de l'enumeration et pour
// etre tres lent sur un poste charge en logiciels.
var uninstallKeys = []string{
	`SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall`,
	`SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall`,
}

func CollectSoftware() []Software {
	var result []Software
	seen := map[string]bool{}

	for _, root := range uninstallKeys {
		result = append(result, readUninstallKey(registry.LOCAL_MACHINE, root, seen)...)
	}
	return result
}

func readUninstallKey(hive registry.Key, path string, seen map[string]bool) []Software {
	var result []Software
	key, err := registry.OpenKey(hive, path, registry.READ)
	if err != nil {
		return result
	}
	defer key.Close()

	names, err := key.ReadSubKeyNames(-1)
	if err != nil {
		return result
	}

	for _, name := range names {
		subKey, err := registry.OpenKey(hive, path+`\`+name, registry.READ)
		if err != nil {
			continue
		}
		displayName, _, _ := subKey.GetStringValue("DisplayName")
		if strings.TrimSpace(displayName) == "" {
			subKey.Close()
			continue
		}
		// SystemComponent=1 marque des composants techniques (redistribuables,
		// correctifs) que Windows lui-meme masque du panneau "Applications et
		// fonctionnalites" - meme filtre applique ici pour un inventaire
		// coherent avec ce que l'utilisateur/l'admin voit deja sur le poste.
		systemComponent, _, _ := subKey.GetIntegerValue("SystemComponent")
		version, _, _ := subKey.GetStringValue("DisplayVersion")
		publisher, _, _ := subKey.GetStringValue("Publisher")
		installDateRaw, _, _ := subKey.GetStringValue("InstallDate")
		subKey.Close()

		if systemComponent == 1 {
			continue
		}
		dedupKey := displayName + "|" + version
		if seen[dedupKey] {
			continue
		}
		seen[dedupKey] = true

		result = append(result, Software{
			Name:        strings.TrimSpace(displayName),
			Version:     strings.TrimSpace(version),
			Publisher:   strings.TrimSpace(publisher),
			InstallDate: formatInstallDate(installDateRaw),
			Source:      "registry",
		})
	}
	return result
}

// formatInstallDate convertit le format brut du registre "YYYYMMDD" en
// "YYYY-MM-DD" (format attendu par le champ Date d'Odoo) - laisse vide si le
// format est absent/invalide plutot que d'envoyer une valeur qu'Odoo
// rejetterait.
func formatInstallDate(raw string) string {
	raw = strings.TrimSpace(raw)
	if len(raw) != 8 {
		return ""
	}
	if _, err := strconv.Atoi(raw); err != nil {
		return ""
	}
	return raw[0:4] + "-" + raw[4:6] + "-" + raw[6:8]
}
