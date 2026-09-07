package actions

import "os/exec"

// Restart/Shutdown passent par le binaire natif shutdown.exe (present sur
// toute edition de Windows) plutot que ExitWindowsEx - shutdown.exe gere
// deja lui-meme l'activation du privilege SE_SHUTDOWN_NAME necessaire, evite
// de dupliquer cette logique de privilege pour un gain marginal. /t 5 laisse
// une fenetre de 5 secondes (visible a l'utilisateur actif via le message
// /c) plutot qu'un arret instantane sans avertissement.
func Restart(reason string) (string, error) {
	return runShutdown("/r", reason)
}

func Shutdown(reason string) (string, error) {
	return runShutdown("/s", reason)
}

func runShutdown(mode, reason string) (string, error) {
	if reason == "" {
		reason = "Demandé via le SIRH Villa Nova"
	}
	cmd := exec.Command("shutdown", mode, "/t", "5", "/c", reason)
	out, err := cmd.CombinedOutput()
	if err != nil {
		return string(out), err
	}
	return "Commande envoyée (redémarrage/arrêt dans 5s).", nil
}
