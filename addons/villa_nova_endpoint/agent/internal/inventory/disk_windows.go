package inventory

import (
	"strings"

	"github.com/yusufpapurcu/wmi"
)

type win32DiskDrive struct {
	Caption      string
	Model        string
	Size         uint64
	SerialNumber string
	MediaType    string
}

func CollectDisks() []Disk {
	var drives []win32DiskDrive
	if err := wmi.Query("SELECT Caption, Model, Size, SerialNumber, MediaType FROM Win32_DiskDrive", &drives); err != nil {
		return nil
	}

	result := make([]Disk, 0, len(drives))
	for _, d := range drives {
		result = append(result, Disk{
			Name:      strings.TrimSpace(d.Caption),
			Model:     strings.TrimSpace(d.Model),
			MediaType: classifyMediaType(d.MediaType, d.Model),
			SizeGB:    round2(float64(d.Size) / (1024 * 1024 * 1024)),
			SerialNo:  strings.TrimSpace(d.SerialNumber),
		})
	}
	return result
}

// classifyMediaType : Win32_DiskDrive.MediaType est peu fiable pour
// distinguer SSD/HDD (souvent juste "Fixed hard disk media" pour les deux) -
// on affine par mots-cles frequents dans le nom de modele en repli, tout en
// restant honnete : 'unknown' si aucun indice fiable.
func classifyMediaType(raw, model string) string {
	lower := strings.ToLower(raw + " " + model)
	switch {
	case strings.Contains(lower, "ssd") || strings.Contains(lower, "nvme") || strings.Contains(lower, "solid state"):
		return "ssd"
	case strings.Contains(lower, "hdd") || strings.Contains(lower, "fixed hard disk"):
		return "hdd"
	default:
		return "unknown"
	}
}
