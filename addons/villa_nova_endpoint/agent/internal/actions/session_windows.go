// session_windows.go permet à l'agent (service LocalSystem, sans session
// interactive propre) d'agir DANS la session de l'utilisateur activement
// connecté - nécessaire pour verrouiller son poste ou lui afficher une
// notification. Utilise uniquement des API Win32 documentées par Microsoft
// (WTS*, jetons, CreateProcessAsUser) via golang.org/x/sys/windows - aucune
// dépendance tierce supplémentaire. Inspiré du mécanisme utilisé par les
// outils d'administration à distance établis (PsExec, agents RMM
// commerciaux) pour exécuter un programme dans le contexte d'un utilisateur
// depuis un service, pas d'une technique exotique.
package actions

import (
	"fmt"
	"unsafe"

	"golang.org/x/sys/windows"
)

const seTcbPrivilege = "SeTcbPrivilege"

var (
	modwtsapi32          = windows.NewLazySystemDLL("wtsapi32.dll")
	procWTSLogoffSession  = modwtsapi32.NewProc("WTSLogoffSession")
)

// enablePrivilege active un privilège sur le jeton du PROCESSUS courant
// (le service lui-même) - WTSQueryUserToken exige SeTcbPrivilege, disponible
// pour LocalSystem mais désactivé par défaut, il faut l'activer
// explicitement avant chaque usage (pas activé une fois pour toutes).
func enablePrivilege(name string) error {
	var token windows.Token
	if err := windows.OpenProcessToken(
		windows.CurrentProcess(), windows.TOKEN_ADJUST_PRIVILEGES|windows.TOKEN_QUERY, &token,
	); err != nil {
		return fmt.Errorf("ouverture du jeton du processus : %w", err)
	}
	defer token.Close()

	var luid windows.LUID
	if err := windows.LookupPrivilegeValue(nil, windows.StringToUTF16Ptr(name), &luid); err != nil {
		return fmt.Errorf("résolution du privilège %s : %w", name, err)
	}

	tp := windows.Tokenprivileges{
		PrivilegeCount: 1,
		Privileges: [1]windows.LUIDAndAttributes{
			{Luid: luid, Attributes: windows.SE_PRIVILEGE_ENABLED},
		},
	}
	if err := windows.AdjustTokenPrivileges(token, false, &tp, 0, nil, nil); err != nil {
		return fmt.Errorf("activation du privilège %s : %w", name, err)
	}
	return nil
}

// activeSessionID trouve la session console active (WTSActive) - celle de
// l'utilisateur physiquement/à distance connecté en ce moment. Renvoie une
// erreur explicite si personne n'est connecté plutôt que d'agir sur une
// session arbitraire (déconnectée/verrouillée).
func activeSessionID() (uint32, error) {
	var sessions *windows.WTS_SESSION_INFO
	var count uint32
	if err := windows.WTSEnumerateSessions(windows.Handle(0), 0, 1, &sessions, &count); err != nil {
		return 0, fmt.Errorf("énumération des sessions : %w", err)
	}
	defer windows.WTSFreeMemory(uintptr(unsafe.Pointer(sessions)))

	entries := unsafe.Slice(sessions, count)
	for _, s := range entries {
		if s.State == windows.WTSActive {
			return s.SessionID, nil
		}
	}
	return 0, fmt.Errorf("aucune session utilisateur active (poste au verrouillage sans session, ou personne connecté)")
}

func activeUserToken() (windows.Token, error) {
	if err := enablePrivilege(seTcbPrivilege); err != nil {
		return 0, err
	}
	sessionID, err := activeSessionID()
	if err != nil {
		return 0, err
	}
	var userToken windows.Token
	if err := windows.WTSQueryUserToken(sessionID, &userToken); err != nil {
		return 0, fmt.Errorf("récupération du jeton utilisateur (session %d) : %w", sessionID, err)
	}
	return userToken, nil
}

// runInActiveUserSession execute commandLine avec les droits de l'utilisateur
// actuellement connecté, attaché à son bureau interactif ("winsta0\\default")
// - c'est ce qui permet à un programme lancé par un service LocalSystem de
// s'afficher réellement à l'écran de l'utilisateur (verrouillage,
// notification), au lieu de s'exécuter invisible en "session 0".
func runInActiveUserSession(commandLine string) error {
	userToken, err := activeUserToken()
	if err != nil {
		return err
	}
	defer userToken.Close()

	var primaryToken windows.Token
	err = windows.DuplicateTokenEx(
		userToken, windows.MAXIMUM_ALLOWED, nil, windows.SecurityImpersonation, windows.TokenPrimary, &primaryToken,
	)
	if err != nil {
		return fmt.Errorf("duplication du jeton en jeton primaire : %w", err)
	}
	defer primaryToken.Close()

	var envBlock *uint16
	if err := windows.CreateEnvironmentBlock(&envBlock, primaryToken, false); err != nil {
		return fmt.Errorf("construction du bloc d'environnement : %w", err)
	}
	defer windows.DestroyEnvironmentBlock(envBlock)

	desktop, err := windows.UTF16PtrFromString(`winsta0\default`)
	if err != nil {
		return err
	}
	cmdLine, err := windows.UTF16PtrFromString(commandLine)
	if err != nil {
		return err
	}

	si := windows.StartupInfo{Cb: uint32(unsafe.Sizeof(windows.StartupInfo{})), Desktop: desktop}
	var pi windows.ProcessInformation

	err = windows.CreateProcessAsUser(
		primaryToken, nil, cmdLine, nil, nil, false,
		windows.CREATE_UNICODE_ENVIRONMENT, envBlock, nil, &si, &pi,
	)
	if err != nil {
		return fmt.Errorf("lancement du processus dans la session utilisateur : %w", err)
	}
	windows.CloseHandle(pi.Process)
	windows.CloseHandle(pi.Thread)
	return nil
}

// Lock verrouille la session de l'utilisateur actif en y exécutant la même
// commande que Windows utilise en interne (Ctrl+Alt+Suppr > Verrouiller).
func Lock() (string, error) {
	if err := runInActiveUserSession(`rundll32.exe user32.dll,LockWorkStation`); err != nil {
		return "", err
	}
	return "Commande de verrouillage envoyée à la session active.", nil
}

// NotifyUser affiche un message à l'utilisateur actif via msg.exe (présent
// nativement sur toute édition de Windows depuis Vista/2008) plutôt qu'une
// boîte de dialogue custom - évite d'avoir à gérer nous-mêmes la fenêtre/le
// rendu dans la session distante.
func NotifyUser(message string) (string, error) {
	if message == "" {
		message = "Message de l'administrateur SIRH Villa Nova."
	}
	sessionID, err := activeSessionID()
	if err != nil {
		return "", err
	}
	cmd := fmt.Sprintf(`msg.exe %d %s`, sessionID, quoteForCmd(message))
	if err := runInActiveUserSession(cmd); err != nil {
		return "", err
	}
	return "Notification envoyée à l'utilisateur actif.", nil
}

// Logoff déconnecte la session active - WTSLogoffSession n'est pas exposé
// par golang.org/x/sys/windows, on le lie nous-mêmes (même approche que le
// module DPAPI de la Phase 2 pour CryptProtectData/CryptUnprotectData).
func Logoff() (string, error) {
	sessionID, err := activeSessionID()
	if err != nil {
		return "", err
	}
	ret, _, callErr := procWTSLogoffSession.Call(0, uintptr(sessionID), 0)
	if ret == 0 {
		return "", fmt.Errorf("WTSLogoffSession (session %d) : %w", sessionID, callErr)
	}
	return fmt.Sprintf("Session %d déconnectée.", sessionID), nil
}

// quoteForCmd echappe une chaine pour un passage securise en argument unique
// a une commande Windows (guillemets doubles, sans interpretation shell -
// CreateProcessAsUser n'invoque pas cmd.exe, pas de risque d'injection de
// metacaracteres shell comme avec un exec.Command("cmd", "/c", ...)).
func quoteForCmd(s string) string {
	escaped := ""
	for _, r := range s {
		if r == '"' {
			escaped += `\"`
		} else {
			escaped += string(r)
		}
	}
	return `"` + escaped + `"`
}
