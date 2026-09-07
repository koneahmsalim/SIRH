// Package inventory collecte l'état matériel/logiciel/réseau réel du poste
// et construit le payload JSON envoyé au serveur (schéma partagé entre
// /endpoint/agent/enroll et /endpoint/agent/checkin - voir
// maintenance_equipment._endpoint_apply_inventory côté Odoo).
package inventory

// Payload est le schéma JSON exact attendu par le serveur Odoo. Toute
// modification ici doit être répercutée dans
// villa_nova_endpoint/models/maintenance_equipment.py::_endpoint_apply_inventory.
type Payload struct {
	Hostname     string `json:"hostname"`
	SerialNo     string `json:"serial_no"`
	OSName       string `json:"os_name"`
	OSVersion    string `json:"os_version"`
	Model        string `json:"model"`
	Platform     string `json:"platform"`
	AgentVersion string `json:"agent_version"`
	LoggedInUser string `json:"logged_in_user"`

	Hardware          Hardware           `json:"hardware"`
	Disks             []Disk             `json:"disks"`
	NetworkInterfaces []NetworkInterface `json:"network_interfaces"`
	Software          []Software         `json:"software"`
	Security          Security           `json:"security"`
}

type Hardware struct {
	CPUModel              string  `json:"cpu_model"`
	CPUCores              int     `json:"cpu_cores"`
	CPULogicalProcessors  int     `json:"cpu_logical_processors"`
	RAMGB                 float64 `json:"ram_gb"`
	Motherboard           string  `json:"motherboard"`
	BIOSVersion           string  `json:"bios_version"`
	GPUModel              string  `json:"gpu_model"`
	BatteryPresent        bool    `json:"battery_present"`
	BatteryHealthPercent  float64 `json:"battery_health_percent"`
	MonitorCount          int     `json:"monitor_count"`
}

type Disk struct {
	Name      string  `json:"name"`
	Model     string  `json:"model"`
	MediaType string  `json:"media_type"`
	SizeGB    float64 `json:"size_gb"`
	SerialNo  string  `json:"serial_no"`
}

type NetworkInterface struct {
	Name         string `json:"name"`
	MACAddress   string `json:"mac_address"`
	IPAddress    string `json:"ip_address"`
	SubnetMask   string `json:"subnet_mask"`
	Gateway      string `json:"gateway"`
	DNSServers   string `json:"dns_servers"`
	DHCPEnabled  bool   `json:"dhcp_enabled"`
	IsPrimary    bool   `json:"is_primary"`
}

type Software struct {
	Name        string `json:"name"`
	Version     string `json:"version"`
	Publisher   string `json:"publisher"`
	InstallDate string `json:"install_date,omitempty"`
	Source      string `json:"source"`
}

type Security struct {
	AVStatus           string `json:"av_status"`
	PatchStatus        string `json:"patch_status"`
	EncryptionEnabled  bool   `json:"encryption_enabled"`
}
