#!/bin/bash
# ---------------------------------------------------------------------------
# Preparation d'un VPS Ubuntu 24.04 pour heberger le SIRH.
#
# A lancer UNE SEULE FOIS, en root, sur un serveur neuf :
#     bash bootstrap_vps.sh
#
# Ce script ne deploie pas l'application : il prepare le terrain (compte de
# service, pare-feu, Docker, protection contre le forcage SSH). Le deploiement
# lui-meme se fait ensuite avec docker compose, sous le compte cree ici.
#
# Il est volontairement idempotent : le relancer ne casse rien.
# ---------------------------------------------------------------------------
set -euo pipefail

UTILISATEUR="${SIRH_USER:-sirh}"

dire() { printf '\n\033[1;36m==> %s\033[0m\n' "$1"; }
avertir() { printf '\033[1;33m /!\\ %s\033[0m\n' "$1"; }

if [ "$(id -u)" -ne 0 ]; then
    echo "Ce script doit etre lance en root." >&2
    exit 1
fi

# --- 1. Mises a jour ------------------------------------------------------
dire "Mise a jour du systeme"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get upgrade -y -qq

dire "Installation des outils de base"
apt-get install -y -qq \
    ca-certificates curl gnupg ufw fail2ban unattended-upgrades \
    postgresql-client-16 htop git

# --- 2. Compte de service -------------------------------------------------
# On ne fait pas tourner l'application en root. Le compte n'a pas de mot de
# passe : on s'y connecte par cle SSH ou via "su - sirh" depuis root.
dire "Compte de service : ${UTILISATEUR}"
if ! id -u "$UTILISATEUR" >/dev/null 2>&1; then
    adduser --disabled-password --gecos "" "$UTILISATEUR"
    echo "  compte cree"
else
    echo "  compte deja present"
fi

# La cle SSH de root est recopiee : sans cela, le compte de service est
# inaccessible a distance et on retombe sur une connexion root permanente.
if [ -f /root/.ssh/authorized_keys ]; then
    install -d -m 700 -o "$UTILISATEUR" -g "$UTILISATEUR" "/home/${UTILISATEUR}/.ssh"
    install -m 600 -o "$UTILISATEUR" -g "$UTILISATEUR" \
        /root/.ssh/authorized_keys "/home/${UTILISATEUR}/.ssh/authorized_keys"
    echo "  cle SSH de root recopiee vers ${UTILISATEUR}"
else
    avertir "Aucune cle SSH dans /root/.ssh/authorized_keys."
    avertir "Ajoutez votre cle AVANT de desactiver la connexion par mot de passe."
fi

# --- 3. Docker ------------------------------------------------------------
dire "Docker"
if ! command -v docker >/dev/null 2>&1; then
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
        | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
        > /etc/apt/sources.list.d/docker.list
    apt-get update -qq
    apt-get install -y -qq docker-ce docker-ce-cli containerd.io \
        docker-buildx-plugin docker-compose-plugin
    echo "  Docker installe"
else
    echo "  Docker deja present : $(docker --version)"
fi
usermod -aG docker "$UTILISATEUR"
systemctl enable --now docker

# --- 4. Pare-feu ----------------------------------------------------------
# Seuls SSH, HTTP et HTTPS sont ouverts. Le port 8069 d'Odoo reste ferme :
# il n'est joignable que depuis la machine elle-meme, derriere le proxy.
dire "Pare-feu"
ufw --force reset >/dev/null
ufw default deny incoming >/dev/null
ufw default allow outgoing >/dev/null
ufw allow OpenSSH >/dev/null
ufw allow 80/tcp >/dev/null
ufw allow 443/tcp >/dev/null
ufw --force enable >/dev/null
ufw status verbose | sed 's/^/  /'

# --- 5. Protection SSH ----------------------------------------------------
dire "fail2ban"
cat > /etc/fail2ban/jail.local <<'CONF'
[sshd]
enabled  = true
maxretry = 5
findtime = 10m
bantime  = 1h
CONF
systemctl enable --now fail2ban >/dev/null
systemctl restart fail2ban
echo "  actif : 5 essais rates -> bannissement 1 h"

# --- 6. Correctifs de securite automatiques -------------------------------
dire "Mises a jour de securite automatiques"
cat > /etc/apt/apt.conf.d/20auto-upgrades <<'CONF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
CONF
echo "  correctifs de securite appliques chaque jour"

# --- 7. Fuseau horaire ----------------------------------------------------
# Le SIRH raisonne en heure d'Abidjan (pointeuse, conges, paie) : le serveur
# doit etre sur le meme fuseau, sinon les journees de presence se decalent.
dire "Fuseau horaire"
timedatectl set-timezone Africa/Abidjan
echo "  $(timedatectl show -p Timezone --value)"

# --- 8. Resume ------------------------------------------------------------
dire "Termine"
cat <<RESUME

  Compte de service : ${UTILISATEUR}   (sudo -iu ${UTILISATEUR})
  Docker            : $(docker --version 2>/dev/null || echo 'non installe')
  Ports ouverts     : 22 (SSH), 80, 443
  Fuseau            : $(timedatectl show -p Timezone --value)
  Nom d'hote        : $(hostname -f 2>/dev/null || hostname)

  ETAPE SUIVANTE
  1. Verifiez que vous pouvez vous connecter en SSH avec le compte ${UTILISATEUR}
     AVANT de fermer cette session root.
  2. Deposez le projet dans /home/${UTILISATEUR}/sirh puis suivez deploy/README.md

RESUME

avertir "La connexion SSH par mot de passe n'a PAS ete desactivee."
avertir "Faites-le seulement apres avoir teste votre cle :"
echo "    sed -i 's/^#*PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config"
echo "    systemctl restart ssh"
