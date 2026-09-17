#!/bin/bash
# ---------------------------------------------------------------------------
# Restaure une archive produite par scripts/backup_sirh.sh sur ce serveur.
#
#     bash deploy/restaurer_sauvegarde.sh sirh_20260917_220000.tar.gz
#
# L'archive contient la base ET le filestore. Les deux sont indissociables :
# restaurer la seule base donne un SIRH dont toutes les pieces jointes sont
# cassees, ce qui ne se voit qu'en ouvrant un dossier du personnel.
#
# Le script REFUSE d'ecraser une base qui contient deja des donnees, sauf
# demande explicite (SIRH_ECRASER=1). C'est le garde-fou le plus utile de
# toute la procedure.
# ---------------------------------------------------------------------------
set -euo pipefail

ARCHIVE="${1:-}"
RACINE=$(cd "$(dirname "$0")/.." && pwd)
COMPOSE="docker compose -f ${RACINE}/deploy/docker-compose.prod.yml"
DB_NAME="${SIRH_DB:-SIRH}"

dire() { printf '\n\033[1;36m==> %s\033[0m\n' "$1"; }
echouer() { printf '\033[0;31mECHEC : %s\033[0m\n' "$1" >&2; exit 1; }

[ -n "$ARCHIVE" ] || echouer "usage : bash deploy/restaurer_sauvegarde.sh <archive.tar.gz>"
[ -f "$ARCHIVE" ] || echouer "archive introuvable : ${ARCHIVE}"

# shellcheck disable=SC1091
set -a; . "${RACINE}/deploy/.env"; set +a
DB_USER="${POSTGRES_USER:-odoo}"

# --- 1. Lecture de l'archive ----------------------------------------------
dire "Lecture de l'archive"
TRAVAIL=$(mktemp -d)
trap 'rm -rf "$TRAVAIL"' EXIT INT TERM
tar -xzf "$ARCHIVE" -C "$TRAVAIL" || echouer "archive illisible"
[ -s "${TRAVAIL}/base.dump" ] || echouer "base.dump absent ou vide"
[ -f "${TRAVAIL}/filestore.tar" ] || echouer "filestore.tar absent"
[ -f "${TRAVAIL}/INFOS.txt" ] && sed 's/^/  /' "${TRAVAIL}/INFOS.txt"
echo "  base    : $(du -h "${TRAVAIL}/base.dump" | cut -f1)"
echo "  fichiers: $(du -h "${TRAVAIL}/filestore.tar" | cut -f1)"

# --- 2. PostgreSQL seul ---------------------------------------------------
# Odoo doit etre arrete : une connexion ouverte empeche de supprimer la base,
# et un Odoo qui ecrit pendant la restauration produit un etat incoherent.
dire "Arret d'Odoo, PostgreSQL seul"
$COMPOSE up -d postgres
$COMPOSE stop odoo 2>/dev/null || true
for _ in $(seq 1 30); do
    if $COMPOSE exec -T postgres pg_isready -U "$DB_USER" -d postgres >/dev/null 2>&1; then break; fi
    sleep 2
done
$COMPOSE exec -T postgres pg_isready -U "$DB_USER" -d postgres >/dev/null 2>&1 \
    || echouer "PostgreSQL ne repond pas"

# --- 3. Garde-fou ---------------------------------------------------------
dire "Etat de la base cible"
TABLES=$($COMPOSE exec -T postgres psql -U "$DB_USER" -d "$DB_NAME" -tAc \
    "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';" 2>/dev/null || echo "0")
echo "  ${DB_NAME} contient ${TABLES} table(s)"
if [ "$TABLES" -gt 0 ] && [ "${SIRH_ECRASER:-0}" != "1" ]; then
    echouer "la base ${DB_NAME} n'est pas vide.
  Si vous voulez VRAIMENT l'ecraser (perte definitive de son contenu) :
      SIRH_ECRASER=1 bash deploy/restaurer_sauvegarde.sh ${ARCHIVE}"
fi

# --- 4. Base --------------------------------------------------------------
dire "Restauration de la base"
$COMPOSE exec -T postgres psql -U "$DB_USER" -d postgres -c \
    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='${DB_NAME}' AND pid <> pg_backend_pid();" >/dev/null 2>&1 || true
$COMPOSE exec -T postgres psql -U "$DB_USER" -d postgres -c "DROP DATABASE IF EXISTS \"${DB_NAME}\";" >/dev/null
$COMPOSE exec -T postgres psql -U "$DB_USER" -d postgres -c "CREATE DATABASE \"${DB_NAME}\" OWNER \"${DB_USER}\";" >/dev/null
$COMPOSE exec -T postgres pg_restore -U "$DB_USER" -d "$DB_NAME" --no-owner --no-privileges \
    < "${TRAVAIL}/base.dump" 2>&1 | grep -vE "already exists|does not exist" || true

TABLES=$($COMPOSE exec -T postgres psql -U "$DB_USER" -d "$DB_NAME" -tAc \
    "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';")
echo "  ${TABLES} table(s) restaurees"
[ "$TABLES" -gt 100 ] || echouer "restauration manifestement incomplete (${TABLES} tables)"

# --- 5. Filestore ---------------------------------------------------------
# Sans lui, la base reference des pieces jointes qui n'existent pas : le SIRH
# demarre normalement et les documents du personnel sont tous casses.
dire "Restauration des pieces jointes"
$COMPOSE run --rm --no-deps -T -u root -v "${TRAVAIL}:/restauration:ro" odoo \
    bash -c "
        mkdir -p /var/lib/odoo/.local/share/Odoo/filestore &&
        rm -rf /var/lib/odoo/.local/share/Odoo/filestore/${DB_NAME} &&
        tar -xf /restauration/filestore.tar -C /var/lib/odoo/.local/share/Odoo/filestore &&
        chown -R odoo:odoo /var/lib/odoo/.local &&
        echo \"  \$(find /var/lib/odoo/.local/share/Odoo/filestore/${DB_NAME} -type f | wc -l) fichier(s)\"
    "

# --- 6. Demarrage ---------------------------------------------------------
dire "Demarrage complet"
$COMPOSE up -d
echo "  en cours de demarrage ; suivez avec :"
echo "      docker compose -f deploy/docker-compose.prod.yml logs -f odoo"

dire "Termine"
cat <<FIN

  A VERIFIER MAINTENANT, dans cet ordre :
    1. https://${SIRH_DOMAIN}  repond et le cadenas est valide
    2. la connexion fonctionne avec un compte existant
    3. une fiche employe affiche bien sa photo  (preuve que le filestore est la)
    4. un rapport de presence se genere en PDF

FIN
