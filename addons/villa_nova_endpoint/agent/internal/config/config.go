// Package config gère la configuration locale persistée de l'agent :
// URL du serveur, identité d'agent obtenue à l'enrôlement, secret chiffré
// au repos via DPAPI (jamais en clair sur disque - voir internal/dpapi).
package config

import (
	"encoding/base64"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"

	"github.com/infinity-africa/villa-nova-endpoint-agent/internal/dpapi"
)

const dirName = `VillaNovaEndpointAgent`
const fileName = `config.json`

type fileFormat struct {
	ServerURL          string `json:"server_url"`
	AgentID             string `json:"agent_id"`
	AgentSecretDPAPI    string `json:"agent_secret_dpapi"` // base64(CryptProtectData(secret))
	CheckinIntervalSeconds int `json:"checkin_interval_seconds"`
}

type Config struct {
	ServerURL              string
	AgentID                string
	AgentSecret            string
	CheckinIntervalSeconds int
}

func path() (string, error) {
	programData := os.Getenv("ProgramData")
	if programData == "" {
		programData = `C:\ProgramData`
	}
	return filepath.Join(programData, dirName, fileName), nil
}

func IsEnrolled() bool {
	_, err := Load()
	return err == nil
}

func Load() (*Config, error) {
	p, err := path()
	if err != nil {
		return nil, err
	}
	raw, err := os.ReadFile(p)
	if err != nil {
		return nil, fmt.Errorf("lecture de la configuration : %w", err)
	}
	var f fileFormat
	if err := json.Unmarshal(raw, &f); err != nil {
		return nil, fmt.Errorf("configuration invalide : %w", err)
	}

	encryptedSecret, err := base64.StdEncoding.DecodeString(f.AgentSecretDPAPI)
	if err != nil {
		return nil, fmt.Errorf("secret d'agent corrompu (base64) : %w", err)
	}
	secretBytes, err := dpapi.Unprotect(encryptedSecret)
	if err != nil {
		return nil, fmt.Errorf("déchiffrement DPAPI du secret d'agent (config liée à cette machine) : %w", err)
	}

	interval := f.CheckinIntervalSeconds
	if interval <= 0 {
		interval = 900
	}
	return &Config{
		ServerURL:              f.ServerURL,
		AgentID:                f.AgentID,
		AgentSecret:            string(secretBytes),
		CheckinIntervalSeconds: interval,
	}, nil
}

func Save(c *Config) error {
	p, err := path()
	if err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Dir(p), 0700); err != nil {
		return fmt.Errorf("création du répertoire de configuration : %w", err)
	}

	encryptedSecret, err := dpapi.Protect([]byte(c.AgentSecret))
	if err != nil {
		return fmt.Errorf("chiffrement DPAPI du secret d'agent : %w", err)
	}

	f := fileFormat{
		ServerURL:              c.ServerURL,
		AgentID:                c.AgentID,
		AgentSecretDPAPI:       base64.StdEncoding.EncodeToString(encryptedSecret),
		CheckinIntervalSeconds: c.CheckinIntervalSeconds,
	}
	raw, err := json.MarshalIndent(f, "", "  ")
	if err != nil {
		return err
	}
	// 0600 : le fichier ne contient plus le secret en clair (chiffré DPAPI),
	// mais reste restreint par défense en profondeur (ACL NTFS gérée par
	// Windows pour ProgramData - LocalSystem/Administrateurs uniquement).
	return os.WriteFile(p, raw, 0600)
}
