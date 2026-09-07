package inventory

import (
	"strings"

	"github.com/yusufpapurcu/wmi"
)

type win32NetworkAdapterConfiguration struct {
	Description      string
	MACAddress       string
	IPAddress        []string
	IPSubnet         []string
	DefaultIPGateway []string
	DNSServerSearchOrder []string
	DHCPEnabled      bool
	IPEnabled        bool
}

func CollectNetworkInterfaces() []NetworkInterface {
	var adapters []win32NetworkAdapterConfiguration
	if err := wmi.Query(
		"SELECT Description, MACAddress, IPAddress, IPSubnet, DefaultIPGateway, DNSServerSearchOrder, DHCPEnabled, IPEnabled FROM Win32_NetworkAdapterConfiguration WHERE IPEnabled = TRUE",
		&adapters,
	); err != nil {
		return nil
	}

	result := make([]NetworkInterface, 0, len(adapters))
	primaryIndex := -1
	for _, a := range adapters {
		if firstIPv4(a.IPAddress) == "" {
			continue
		}
		iface := NetworkInterface{
			Name:        strings.TrimSpace(a.Description),
			MACAddress:  a.MACAddress,
			IPAddress:   firstIPv4(a.IPAddress),
			SubnetMask:  firstOrEmpty(a.IPSubnet),
			Gateway:     firstOrEmpty(a.DefaultIPGateway),
			DNSServers:  strings.Join(a.DNSServerSearchOrder, ","),
			DHCPEnabled: a.DHCPEnabled,
		}
		if primaryIndex == -1 && len(a.DefaultIPGateway) > 0 {
			primaryIndex = len(result)
		}
		result = append(result, iface)
	}
	// Aucune interface avec passerelle par defaut trouvee (rare, ex. poste
	// isole sur un reseau statique sans route par defaut) : la premiere
	// interface IP-activee sert de repli plutot que de laisser aucune
	// interface primaire.
	if primaryIndex == -1 && len(result) > 0 {
		primaryIndex = 0
	}
	if primaryIndex >= 0 {
		result[primaryIndex].IsPrimary = true
	}
	return result
}

func firstIPv4(addresses []string) string {
	for _, addr := range addresses {
		if strings.Count(addr, ".") == 3 {
			return addr
		}
	}
	return ""
}

func firstOrEmpty(values []string) string {
	if len(values) == 0 {
		return ""
	}
	return values[0]
}
