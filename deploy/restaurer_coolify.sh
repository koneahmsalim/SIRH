#!/bin/bash
# ---------------------------------------------------------------------------
# Restaure une archive de scripts/backup_sirh.sh dans une pile geree par
# Coolify.
#
#     SIRH_PG_CONTAINER=xxx-postgres-1 \
#     SIRH_ODOO_CONTAINER=xxx-odoo-1 \
#     bash deploy/restaurer_coolify.sh sirh_20260918_220000.tar.gz
#
# Coolify nomme les conteneurs lui-meme ; on ne peut donc pas passer par
# "docker compose" comme dans la pile autonome. Relevez les noms avec :
#     docker ps --format '{{.Names}}' | grep -Ei 'odoo|postgres'
#
# L'archive contient la base ET le filestore. Les deux sont indissociables :
# restaurer la seule base donne un SIRH dont toutes les pieces jointes sont
# cassees, ce qui ne se voit qu'en ouvrant un dossier du personnel.
# ---------------------------------------------------------------------------
set -euo pipefail

ARCHIVE="${1:-}"
PG="${SIRH_PG_CONTAINER:-}"
ODOO="${SIRH_ODOO_CONTAINER:-}"
DB_NAME="${SIRH_DB:-SIRH}"
DB_USER="${SIRH_DB_USER:-odoo}"

dire() { printf '\n\033[1;36m==> %s\033[0m\n' "$1"; }
echouer() { printf '\033[0;31mECHEC : %s\033[0m\n' "$1" >&2; exit 1; }

[ -n "$ARCHIVE" ] || echouer "usage : bash deploy/restaurer_coolify.sh <archive.tar.gz>"
[ -f "$ARCHIVE" ] || echouer "archive introuvable : ${ARCHIVE}"
[ -n "$PG" ] || echouer "definissez SIRH_PG_CONTAINER (docker ps --format '{{.Names}}')"
[ -n "$ODOO" ] || echouer "definissez SIRH_ODOO_CONTAINER"
docker inspect "$PG" >/dev/null 2>&1 || echouer "conteneur PostgreSQL introuvable : ${PG}"
docker inspect "$ODOO" >/dev/null 2>&1 || echouer "conteneur Odoo introuvable : ${ODOO}"

# --- 1. Lecture de l'archive ----------------------------------------------
dire "Lecture de l'archive"
TRAVAIL=$(mktemp -d)
trap 'rm -rf "$TRAVAIL"' EXIT INT TERM
tar -xzf "$ARCHIVE" -C "$TRAVAIL" || echouer "archive illisible"
[ -s "${TRAVAIL}/base.dump" ] || echouer "base.dump absent ou vide"
[ -f "${TRAVAIL}/filestore.tar" ] || echouer "filestore.tar absent"
[ -f "${TRAVAIL}/INFOS.txt" ] && sed 's/^/  /' "${TRAVAIL}/INFOS.txt"
echo "  base     : $(du -h "${TRAVAIL}/base.dump" | cut -f1)"
echo "  fichiers : $(du -h "${TRAVAIL}/filestore.tar" | cut -f1)"

# --- 2. Arret d'Odoo ------------------------------------------------------
# Une connexion ouverte empeche de supprimer la base, et un Odoo qui ecrit
# pendant la restauration produit un etat incoherent.
dire "Arret d'Odoo"
docker stop "$ODOO" >/dev/null
echo "  ${ODOO} arrete"
redemarrer_odoo() { docker start "$ODOO" >/dev/null 2>&1 || true; }
trap 'redemarrer_odoo; rm -rf "$TRAVAIL"' EXIT INT TERM

docker exec "$PG" pg_isready -U "$DB_USER" -d postgres >/dev/null 2>&1 \
    || echouer "PostgreSQL ne repond pas dans ${PG}"

# --- 3. Garde-fou ---------------------------------------------------------
dire "Etat de la base cible"
TABLES=$(docker exec "$PG" psql -U "$DB_USER" -d "$DB_NAME" -tAc \
    "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';" 2>/dev/null || echo "0")
echo "  ${DB_NAME} contient ${TABLES} table(s)"
if [ "$TABLES" -gt 0 ] && [ "${SIRH_ECRASER:-0}" != "1" ]; then
    echouer "la base ${DB_NAME} n'est pas vide.
  Pour l'ecraser VRAIMENT (perte definitive de son contenu), relancez avec :
      SIRH_ECRASER=1 SIRH_PG_CONTAINER=${PG} SIRH_ODOO_CONTAINER=${ODOO} \\
      bash deploy/restaurer_coolify.sh ${ARCHIVE}"
fi

# --- 4. Base --------------------------------------------------------------
dire "Restauration de la base"
docker exec "$PG" psql -U "$DB_USER" -d postgres -c \
    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='${DB_NAME}' AND pid <> pg_backend_pid();" >/dev/null 2>&1 || true
docker exec "$PG" psql -U "$DB_USER" -d postgres -c "DROP DATABASE IF EXISTS \"${DB_NAME}\";" >/dev/null
docker exec "$PG" psql -U "$DB_USER" -d postgres -c "CREATE DATABASE \"${DB_NAME}\" OWNER \"${DB_USER}\";" >/dev/null
docker exec -i "$PG" pg_restore -U "$DB_USER" -d "$DB_NAME" --no-owner --no-privileges \
    < "${TRAVAIL}/base.dump" 2>&1 | grep -vE "already exists|does not exist" || true

TABLES=$(docker exec "$PG" psql -U "$DB_USER" -d "$DB_NAME" -tAc \
    "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';")
echo "  ${TABLES} table(s) restaurees"
[ "$TABLES" -gt 100 ] || echouer "restauration manifestement incomplete (${TABLES} tables)"

# --- 5. Filestore ---------------------------------------------------------
# Odoo est arrete : on copie dans son volume via un conteneur temporaire qui
# partage ses volumes, ce qui evite de deviner le chemin du volume sur l'hote.
dire "Restauration des pieces jointes"
docker run --rm -u 0 --volumes-from "$ODOO" \
    -v "${TRAVAIL}:/restauration:ro" alpine:3 \
    sh -c "
        mkdir -p /var/lib/odoo/.local/share/Odoo/filestore &&
        rm -rf /var/lib/odoo/.local/share/Odoo/filestore/${DB_NAME} &&
        tar -xf /restauration/filestore.tar -C /var/lib/odoo/.local/share/Odoo/filestore &&
        chown -R 101:101 /var/lib/odoo/.local &&
        echo \"  \$(find /var/lib/odoo/.local/share/Odoo/filestore/${DB_NAME} -type f | wc -l) fichier(s)\"
    "

# --- 6. Redemarrage -------------------------------------------------------
dire "Redemarrage d'Odoo"
trap 'rm -rf "$TRAVAIL"' EXIT INT TERM
docker start "$ODOO" >/dev/null
echo "  suivez le demarrage :  docker logs -f ${ODOO}"

dire "Termine"
cat <<'FIN'

  A VERIFIER MAINTENANT, dans cet ordre :
    1. le site repond en https, cadenas valide
    2. la connexion fonctionne avec un compte existant
    3. une fiche employe affiche sa photo  (preuve que le filestore est la)
    4. un rapport de presence se genere en PDF
    5. le chatter d'une tache se met a jour sans rafraichir  (route /websocket)

FIN
