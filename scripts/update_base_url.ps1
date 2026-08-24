<#
.SYNOPSIS
    Garde web.base.url (Odoo) synchronise avec l'IP LAN reelle de la machine.

.DESCRIPTION
    Sans cela, tous les liens generes par Odoo (invitations, reinitialisation
    de mot de passe, notifications) restent fondes sur l'IP figee dans
    ir_config_parameter au moment ou elle a ete definie - si le bail DHCP
    change (redemarrage, reconnexion Wi-Fi), les liens deviennent morts pour
    quiconque n'est pas sur la meme machine que le serveur.

    Detection de l'IP : on prend l'adresse de l'interface qui possede
    reellement une passerelle par defaut active, plutot qu'un nom d'adaptateur
    fixe (Wi-Fi, Ethernet...) - sur cette machine, la route par defaut passe
    par un commutateur virtuel Hyper-V bridge sur le Wi-Fi, pas sur
    l'adaptateur "Wi-Fi" lui-meme.
#>

$ComposeDir = "C:\Users\kbrah\Desktop\LA BOITE A OUTILS\odoo18-hrms"
$OdooPort = 8069
$LogFile = Join-Path $ComposeDir "scripts\update_base_url.log"

function Write-Log($message) {
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $message"
    Add-Content -Path $LogFile -Value $line
}

try {
    $config = Get-NetIPConfiguration | Where-Object {
        $_.IPv4DefaultGateway -and $_.NetAdapter.Status -eq "Up"
    } | Select-Object -First 1

    if (-not $config) {
        Write-Log "Aucune interface avec passerelle active trouvee - abandon."
        exit 0
    }

    $currentIp = $config.IPv4Address.IPAddress
    $newBaseUrl = "http://${currentIp}:${OdooPort}"

    Push-Location $ComposeDir
    try {
        # Le script vit dans ./addons (monte sur /mnt/extra-addons), execute
        # via une redirection bash *dans* le conteneur - piper une chaine
        # PowerShell directement dans le stdin de "docker compose exec" ne
        # marche pas de facon fiable (stdin coupe en cours de lecture cote
        # odoo shell, observe en test).
        $output = docker compose exec -T -e NEW_BASE_URL=$newBaseUrl odoo bash -c "odoo shell -d SIRH --no-http < /mnt/extra-addons/_scripts/update_base_url.py" 2>$null
        $result = $output | Select-String -Pattern "^(CHANGED|UNCHANGED|MISSING_NEW_BASE_URL)"
        if ($result) {
            Write-Log "IP detectee: $currentIp | $result"
        } else {
            Write-Log "IP detectee: $currentIp | Pas de confirmation dans la sortie (voir ci-dessous)"
            Write-Log ($output -join " | ")
        }
    } finally {
        Pop-Location
    }
} catch {
    Write-Log "ERREUR: $($_.Exception.Message)"
}
