// Package client parle au serveur Odoo (villa_nova_endpoint) en HTTPS
// sortant uniquement - l'agent n'ouvre jamais de port, ne reçoit jamais de
// connexion entrante (conforme à l'objectif 2 du brief RMM : l'agent
// interroge le serveur, jamais l'inverse).
package client

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"

	"github.com/infinity-africa/villa-nova-endpoint-agent/internal/inventory"
)

type Client struct {
	ServerURL  string
	HTTPClient *http.Client
}

func New(serverURL string) *Client {
	return &Client{
		ServerURL:  serverURL,
		HTTPClient: &http.Client{Timeout: 30 * time.Second},
	}
}

type EnrollResponse struct {
	AgentID                string `json:"agent_id"`
	AgentSecret            string `json:"agent_secret"`
	EquipmentID            int    `json:"equipment_id"`
	CheckinIntervalSeconds int    `json:"checkin_interval_seconds"`
	Error                  string `json:"error"`
}

type CheckinResponse struct {
	Status                 string   `json:"status"`
	CheckinIntervalSeconds int      `json:"checkin_interval_seconds"`
	Commands               []string `json:"commands"`
	Error                  string   `json:"error"`
}

func (c *Client) Enroll(enrollmentKey string, payload inventory.Payload) (*EnrollResponse, error) {
	body, err := json.Marshal(payload)
	if err != nil {
		return nil, err
	}
	req, err := http.NewRequest(http.MethodPost, c.ServerURL+"/endpoint/agent/enroll", bytes.NewReader(body))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-Enrollment-Key", enrollmentKey)

	resp, err := c.HTTPClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("appel /endpoint/agent/enroll : %w", err)
	}
	defer resp.Body.Close()

	raw, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}
	var out EnrollResponse
	if err := json.Unmarshal(raw, &out); err != nil {
		return nil, fmt.Errorf("réponse d'enrôlement invalide (HTTP %d) : %s", resp.StatusCode, string(raw))
	}
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("enrôlement refusé (HTTP %d) : %s", resp.StatusCode, out.Error)
	}
	return &out, nil
}

func (c *Client) Checkin(agentID, agentSecret string, payload inventory.Payload) (*CheckinResponse, error) {
	body, err := json.Marshal(payload)
	if err != nil {
		return nil, err
	}
	req, err := http.NewRequest(http.MethodPost, c.ServerURL+"/endpoint/agent/checkin", bytes.NewReader(body))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-Agent-Id", agentID)
	req.Header.Set("X-Agent-Secret", agentSecret)

	resp, err := c.HTTPClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("appel /endpoint/agent/checkin : %w", err)
	}
	defer resp.Body.Close()

	raw, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}
	var out CheckinResponse
	if err := json.Unmarshal(raw, &out); err != nil {
		return nil, fmt.Errorf("réponse de check-in invalide (HTTP %d) : %s", resp.StatusCode, string(raw))
	}
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("check-in refusé (HTTP %d) : %s", resp.StatusCode, out.Error)
	}
	return &out, nil
}
