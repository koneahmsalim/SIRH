package actions

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"time"
)

const scriptExecutionTimeout = 5 * time.Minute

// RunScript execute un script PowerShell APPROUVE (cure par un admin, jamais
// une chaine libre - voir itsm.approved.script cote serveur) - verifie que
// le contenu recu correspond bien a l'empreinte annoncee AVANT toute
// execution (defense en profondeur : meme si le transport est deja protege
// par TLS en production, un contenu qui ne correspond pas a son empreinte
// annoncee ne doit jamais s'executer). Un timeout borne (5 min) evite qu'un
// script bloque l'agent indefiniment.
func RunScript(content, expectedHash string) (string, error) {
	if content == "" {
		return "", fmt.Errorf("contenu de script vide")
	}
	actualHash := sha256.Sum256([]byte(content))
	actualHashHex := hex.EncodeToString(actualHash[:])
	if expectedHash != "" && actualHashHex != expectedHash {
		return "", fmt.Errorf(
			"empreinte du script incorrecte (attendu %s, reçu %s) - exécution refusée",
			expectedHash, actualHashHex)
	}

	tmpDir, err := os.MkdirTemp("", "vn-script-*")
	if err != nil {
		return "", fmt.Errorf("création du répertoire temporaire : %w", err)
	}
	defer os.RemoveAll(tmpDir)

	scriptPath := filepath.Join(tmpDir, "script.ps1")
	if err := os.WriteFile(scriptPath, []byte(content), 0600); err != nil {
		return "", fmt.Errorf("écriture du fichier script temporaire : %w", err)
	}

	ctx, cancel := context.WithTimeout(context.Background(), scriptExecutionTimeout)
	defer cancel()

	cmd := exec.CommandContext(ctx, "powershell.exe",
		"-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", scriptPath)
	out, err := cmd.CombinedOutput()
	output := string(out)
	if ctx.Err() == context.DeadlineExceeded {
		return output, fmt.Errorf("script interrompu après %s (délai dépassé)", scriptExecutionTimeout)
	}
	if err != nil {
		return output, fmt.Errorf("échec de l'exécution du script : %w", err)
	}
	return output, nil
}
