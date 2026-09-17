#!/bin/bash
# ---------------------------------------------------------------------------
# Prepare les fichiers de configuration de production SUR LE SERVEUR.
#
#     bash deploy/preparer_production.sh
#
# Genere deux fichiers, tous deux ignores par git :
#   deploy/.env                 mots de passe et nom d'hote
#   deploy/odoo.runtime.conf    odoo.prod.conf + un mot de passe maitre tire au sort
#
# Relancer le script ne regenere PAS les secrets deja en place : on ne veut pas
# qu'une seconde execution invalide le mot de passe de la base et rende
# l'instance inaccessible.
# ---------------------------------------------------------------------------
set -euo pipefail

RACINE=$(cd "$(dirname "$0")/.." && pwd)
DEPLOY="${RACINE}/deploy"

dire() { printf '\n\033[1;36m==> %s\033[0m\n' "$1"; }

aleatoire() { openssl rand -base64 36 | tr -d '\n/+=' | cut -c1-32; }

# --- 1. .env --------------------------------------------------------------
dire "Fichier d'environnement"
if [ -f "${DEPLOY}/.env" ]; then
    echo "  deploy/.env existe deja, laisse intact."
else
    NOM_HOTE=$(hostname -f 2>/dev/null || hostname)
    MDP_PG=$(aleatoire)
    cat > "${DEPLOY}/.env" <<CONF
POSTGRES_USER=odoo
POSTGRES_PASSWORD=${MDP_PG}
SIRH_DOMAIN=${NOM_HOTE}
SIRH_ADMIN_EMAIL=ahmed.kone@infinity-africa.com
CONF
    chmod 600 "${DEPLOY}/.env"
    echo "  cree, avec un mot de passe PostgreSQL tire au sort."
    echo "  nom d'hote detecte : ${NOM_HOTE}"
    echo "  VERIFIEZ ce nom : c'est lui que Caddy presentera a Let's Encrypt."
fi

# --- 2. Configuration Odoo ------------------------------------------------
dire "Configuration Odoo"
if [ -f "${DEPLOY}/odoo.runtime.conf" ]; then
    echo "  deploy/odoo.runtime.conf existe deja, laisse intact."
else
    MDP_MAITRE=$(aleatoire)
    sed "s|^admin_passwd = REMPLACER_AVANT_DEMARRAGE$|admin_passwd = ${MDP_MAITRE}|" \
        "${DEPLOY}/odoo.prod.conf" > "${DEPLOY}/odoo.runtime.conf"
    chmod 600 "${DEPLOY}/odoo.runtime.conf"
    if grep -q "REMPLACER_AVANT_DEMARRAGE" "${DEPLOY}/odoo.runtime.conf"; then
        echo "  ECHEC : le marqueur admin_passwd n'a pas ete remplace." >&2
        rm -f "${DEPLOY}/odoo.runtime.conf"
        exit 1
    fi
    echo "  cree, avec un mot de passe maitre tire au sort."
fi

# --- 3. Controles ---------------------------------------------------------
dire "Controles"
erreurs=0

verifier() {
    if grep -qE "$2" "$1"; then
        printf '  \033[0;32mOK\033[0m   %s\n' "$3"
    else
        printf '  \033[0;31mNON\033[0m  %s\n' "$3"
        erreurs=$((erreurs + 1))
    fi
}

verifier "${DEPLOY}/odoo.runtime.conf" '^list_db = False$'   "les bases ne sont pas listees publiquement"
verifier "${DEPLOY}/odoo.runtime.conf" '^dbfilter = \^SIRH\$$' "une seule base servie"
verifier "${DEPLOY}/odoo.runtime.conf" '^proxy_mode = True$'  "en-tetes du proxy pris en compte"
verifier "${DEPLOY}/odoo.runtime.conf" '^workers = [1-9]'     "mode multi-processus actif"

if grep -qE '^admin_passwd = (REMPLACER_AVANT_DEMARRAGE|cosmic_admin|admin)$' "${DEPLOY}/odoo.runtime.conf"; then
    printf '  \033[0;31mNON\033[0m  mot de passe maitre encore faible\n'
    erreurs=$((erreurs + 1))
else
    printf '  \033[0;32mOK\033[0m   mot de passe maitre non trivial\n'
fi

if grep -qE '^POSTGRES_PASSWORD=(odoo|postgres|CHANGEZ_MOI.*)$' "${DEPLOY}/.env"; then
    printf '  \033[0;31mNON\033[0m  mot de passe PostgreSQL encore trivial\n'
    erreurs=$((erreurs + 1))
else
    printf '  \033[0;32mOK\033[0m   mot de passe PostgreSQL non trivial\n'
fi

echo ""
if [ "$erreurs" -gt 0 ]; then
    echo "  ${erreurs} point(s) a corriger avant de demarrer." >&2
    exit 1
fi

dire "Pret"
cat <<FIN

  Les secrets sont dans deploy/.env et deploy/odoo.runtime.conf (chmod 600,
  tous deux ignores par git).

  Relevez et conservez le mot de passe maitre ailleurs qu'ici :
      grep admin_passwd deploy/odoo.runtime.conf

  ETAPE SUIVANTE : restaurer la base, puis
      docker compose -f deploy/docker-compose.prod.yml up -d --build

FIN
