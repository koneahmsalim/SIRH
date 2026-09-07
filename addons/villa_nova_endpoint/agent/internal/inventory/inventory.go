package inventory

// Collect assemble un Payload complet en interrogeant WMI (materiel,
// reseau, disques, securite) et le registre (logiciels installes). Utilise
// a la fois par l'enrolement et par chaque check-in - le meme inventaire
// complet est toujours envoye, jamais de version "allegee" pour le
// check-in : simplicite du protocole plutot qu'une optimisation de bande
// passante prematuree (le payload JSON d'un poste type reste de l'ordre de
// quelques dizaines de Ko, meme avec 150-200 logiciels installes).
func Collect(agentVersion string) Payload {
	hostname, serialNo, model, osName, osVersion, loggedInUser := CollectSystemIdentity()

	return Payload{
		Hostname:          hostname,
		SerialNo:          serialNo,
		OSName:            osName,
		OSVersion:         osVersion,
		Model:             model,
		Platform:          "windows",
		AgentVersion:      agentVersion,
		LoggedInUser:      loggedInUser,
		Hardware:          CollectHardware(),
		Disks:             CollectDisks(),
		NetworkInterfaces: CollectNetworkInterfaces(),
		Software:          CollectSoftware(),
		Security:          CollectSecurity(),
	}
}
