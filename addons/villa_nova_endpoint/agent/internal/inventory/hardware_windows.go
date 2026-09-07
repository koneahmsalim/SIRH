package inventory

import (
	"strings"

	"github.com/yusufpapurcu/wmi"
)

type win32Processor struct {
	Name                      string
	NumberOfCores             uint32
	NumberOfLogicalProcessors uint32
}

type win32PhysicalMemory struct {
	Capacity uint64
}

type win32BaseBoard struct {
	Manufacturer string
	Product      string
}

type win32BIOS struct {
	SMBIOSBIOSVersion string
	SerialNumber      string
}

type win32VideoController struct {
	Name string
}

type win32ComputerSystem struct {
	Name     string
	Model    string
	UserName string
}

type win32OperatingSystem struct {
	Caption string
	Version string
	BuildNumber string
}

// batteryStaticData/batteryFullChargedCapacity vivent dans le namespace
// root/wmi (pas root/cimv2) - c'est la seule source fiable pour une VRAIE
// sante de batterie (capacite pleine actuelle / capacite de conception),
// contrairement a Win32_Battery.EstimatedChargeRemaining qui n'est que le
// niveau de charge instantane, pas un indicateur d'usure.
type batteryStaticData struct {
	InstanceName    string
	DesignedCapacity uint32
}

type batteryFullChargedCapacity struct {
	InstanceName        string
	FullChargedCapacity uint32
}

// wmiMonitorID (namespace root/wmi) : detection best-effort - depend du
// pilote graphique/moniteur installe, peut renvoyer une liste vide sur
// certaines machines (VM, RDP, pilotes generiques) sans que ce soit une
// erreur d'agent.
type wmiMonitorID struct {
	InstanceName string
}

func CollectHardware() Hardware {
	h := Hardware{}

	var cpus []win32Processor
	if err := wmi.Query("SELECT Name, NumberOfCores, NumberOfLogicalProcessors FROM Win32_Processor", &cpus); err == nil && len(cpus) > 0 {
		h.CPUModel = strings.TrimSpace(cpus[0].Name)
		h.CPUCores = int(cpus[0].NumberOfCores)
		h.CPULogicalProcessors = int(cpus[0].NumberOfLogicalProcessors)
	}

	var mem []win32PhysicalMemory
	if err := wmi.Query("SELECT Capacity FROM Win32_PhysicalMemory", &mem); err == nil {
		var totalBytes uint64
		for _, m := range mem {
			totalBytes += m.Capacity
		}
		h.RAMGB = round2(float64(totalBytes) / (1024 * 1024 * 1024))
	}

	var boards []win32BaseBoard
	if err := wmi.Query("SELECT Manufacturer, Product FROM Win32_BaseBoard", &boards); err == nil && len(boards) > 0 {
		h.Motherboard = strings.TrimSpace(boards[0].Manufacturer + " " + boards[0].Product)
	}

	var bios []win32BIOS
	if err := wmi.Query("SELECT SMBIOSBIOSVersion, SerialNumber FROM Win32_BIOS", &bios); err == nil && len(bios) > 0 {
		h.BIOSVersion = strings.TrimSpace(bios[0].SMBIOSBIOSVersion)
	}

	var gpus []win32VideoController
	if err := wmi.Query("SELECT Name FROM Win32_VideoController", &gpus); err == nil && len(gpus) > 0 {
		names := make([]string, 0, len(gpus))
		for _, g := range gpus {
			if strings.TrimSpace(g.Name) != "" {
				names = append(names, strings.TrimSpace(g.Name))
			}
		}
		h.GPUModel = strings.Join(names, ", ")
	}

	h.BatteryHealthPercent, h.BatteryPresent = collectBatteryHealth()
	h.MonitorCount = collectMonitorCount()

	return h
}

func collectBatteryHealth() (float64, bool) {
	var designed []batteryStaticData
	var full []batteryFullChargedCapacity
	errDesigned := wmi.QueryNamespace("SELECT InstanceName, DesignedCapacity FROM BatteryStaticData", &designed, `root\wmi`)
	errFull := wmi.QueryNamespace("SELECT InstanceName, FullChargedCapacity FROM BatteryFullChargedCapacity", &full, `root\wmi`)
	if errDesigned != nil || errFull != nil || len(designed) == 0 || len(full) == 0 {
		return 0, false
	}
	designedCap := designed[0].DesignedCapacity
	fullCap := full[0].FullChargedCapacity
	if designedCap == 0 {
		return 0, true
	}
	health := round2(float64(fullCap) / float64(designedCap) * 100.0)
	if health > 100 {
		health = 100
	}
	return health, true
}

func collectMonitorCount() int {
	var monitors []wmiMonitorID
	if err := wmi.QueryNamespace("SELECT InstanceName FROM WmiMonitorID", &monitors, `root\wmi`); err != nil {
		return 0
	}
	return len(monitors)
}

func CollectSystemIdentity() (hostname, serialNo, model, osName, osVersion, loggedInUser string) {
	var bios []win32BIOS
	if err := wmi.Query("SELECT SerialNumber FROM Win32_BIOS", &bios); err == nil && len(bios) > 0 {
		serialNo = strings.TrimSpace(bios[0].SerialNumber)
	}

	var cs []win32ComputerSystem
	if err := wmi.Query("SELECT Name, Model, UserName FROM Win32_ComputerSystem", &cs); err == nil && len(cs) > 0 {
		hostname = strings.TrimSpace(cs[0].Name)
		model = strings.TrimSpace(cs[0].Model)
		loggedInUser = strings.TrimSpace(cs[0].UserName)
	}

	var os []win32OperatingSystem
	if err := wmi.Query("SELECT Caption, Version, BuildNumber FROM Win32_OperatingSystem", &os); err == nil && len(os) > 0 {
		osName = strings.TrimSpace(os[0].Caption)
		osVersion = strings.TrimSpace(os[0].Version) + " (Build " + strings.TrimSpace(os[0].BuildNumber) + ")"
	}

	return
}

func round2(v float64) float64 {
	return float64(int(v*100+0.5)) / 100
}
