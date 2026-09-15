#!/bin/sh
# ---------------------------------------------------------------------------
# Sauvegarde complete du SIRH : base PostgreSQL + filestore Odoo.
#
# Les deux sont indissociables. Le filestore contient les pieces jointes
# (documents du personnel, photos, CV) : la base ne stocke que leur reference.
# Une sauvegarde de la seule base restaure donc un SIRH dont toutes les pieces
# jointes sont cassees - c'est le defaut des dumps presents dans ce projet
# avant l'ecriture de ce script.
#
# Les deux sont volontairement places dans UNE SEULE archive horodatee : des
# fichiers separes finissent toujours par etre restaures en couples depareilles.
#
# Usage :   ./scripts/backup_sirh.sh [repertoire_de_destination]
# Cron   :  30 22 * * *  /chemin/vers/scripts/backup_sirh.sh >> /var/log/sirh_backup.log 2>&1
# ---------------------------------------------------------------------------
set -eu

# Git Bash (MSYS) reecrit tout argument ressemblant a un chemin Unix avant de
# le passer a docker : "/var/lib/odoo/..." devient "C:/Program Files/Git/var/...".
# Le test d'existence du filestore echouait donc systematiquement sous Windows,
# et la sauvegarde se faisait SANS les pieces jointes, sans que rien ne bloque.
# Sans effet sur Linux, ou la variable est simplement ignoree.
export MSYS_NO_PATHCONV=1

DB_NAME="${SIRH_DB:-SIRH}"
DB_USER="${SIRH_DB_USER:-odoo}"
CONTENEUR_PG="${SIRH_PG_CONTAINER:-odoo18-hrms-postgres-1}"
CONTENEUR_ODOO="${SIRH_ODOO_CONTAINER:-odoo18-hrms-odoo-1}"
FILESTORE="/var/lib/odoo/.local/share/Odoo/filestore/${DB_NAME}"
RETENTION_JOURS="${SIRH_RETENTION:-7}"

DESTINATION="${1:-$(dirname "$0")/../backups}"
HORODATAGE=$(date +%Y%m%d_%H%M%S)
ARCHIVE="${DESTINATION}/sirh_${HORODATAGE}.tar.gz"
TRAVAIL=$(mktemp -d)

nettoyer() { rm -rf "$TRAVAIL"; }
trap nettoyer EXIT INT TERM

echo "[$(date '+%F %T')] Sauvegarde de ${DB_NAME}"
mkdir -p "$DESTINATION"

# --- Verification prealable de la place disponible --------------------------
# Inutile de lancer un dump de plusieurs centaines de Mo pour le voir echouer
# a mi-parcours et laisser une archive tronquee qui a l'air valide.
DISPO_MO=$(df -Pm "$DESTINATION" | awk 'NR==2 {print $4}')
if [ "$DISPO_MO" -lt 500 ]; then
    echo "  ECHEC : seulement ${DISPO_MO} Mo disponibles sur la destination (500 Mo requis)." >&2
    exit 1
fi

# --- 1. Base de donnees -----------------------------------------------------
# Format "custom" (-Fc) : compresse, et restaurable table par table avec
# pg_restore, ce qu'un dump SQL brut ne permet pas.
echo "  base de donnees..."
docker exec "$CONTENEUR_PG" pg_dump -U "$DB_USER" -Fc -d "$DB_NAME" > "${TRAVAIL}/base.dump"
if [ ! -s "${TRAVAIL}/base.dump" ]; then
    echo "  ECHEC : le dump est vide." >&2
    exit 1
fi

# --- 2. Filestore -----------------------------------------------------------
echo "  filestore..."
if docker exec "$CONTENEUR_ODOO" test -d "$FILESTORE"; then
    docker exec "$CONTENEUR_ODOO" tar -cf - -C "$(dirname "$FILESTORE")" "$(basename "$FILESTORE")" \
        > "${TRAVAIL}/filestore.tar"
elif [ "${SIRH_ALLOW_NO_FILESTORE:-0}" = "1" ]; then
    # Cas legitime d'une base encore sans aucune piece jointe, a demander
    # explicitement.
    echo "  filestore absent, ignore sur demande explicite."
    tar -cf "${TRAVAIL}/filestore.tar" -T /dev/null
else
    # Par defaut on ARRETE. Une sauvegarde amputee du filestore restaure un
    # SIRH dont toutes les pieces jointes sont cassees, alors qu'elle a toutes
    # les apparences d'une sauvegarde valide - le pire des deux mondes.
    echo "  ECHEC : filestore introuvable (${FILESTORE})." >&2
    echo "  Verifiez le chemin, ou relancez avec SIRH_ALLOW_NO_FILESTORE=1 si" >&2
    echo "  cette base n'a reellement aucune piece jointe." >&2
    exit 1
fi

# --- 3. Archive unique ------------------------------------------------------
printf 'base=%s\ndate=%s\nfilestore=%s\n' "$DB_NAME" "$HORODATAGE" "$FILESTORE" > "${TRAVAIL}/INFOS.txt"
tar -czf "$ARCHIVE" -C "$TRAVAIL" base.dump filestore.tar INFOS.txt

# --- 4. Verification --------------------------------------------------------
# Une archive qu'on n'a jamais ouverte n'est pas une sauvegarde, c'est un pari.
if ! tar -tzf "$ARCHIVE" >/dev/null 2>&1; then
    echo "  ECHEC : l'archive produite est illisible, suppression." >&2
    rm -f "$ARCHIVE"
    exit 1
fi

TAILLE=$(du -h "$ARCHIVE" | cut -f1)
echo "  OK : ${ARCHIVE} (${TAILLE})"

# --- 5. Rotation ------------------------------------------------------------
# Sans rotation, la sauvegarde finit par remplir le disque et faire tomber le
# service qu'elle etait censee proteger.
SUPPRIMEES=$(find "$DESTINATION" -maxdepth 1 -name 'sirh_*.tar.gz' -mtime "+${RETENTION_JOURS}" -print -delete | wc -l)
[ "$SUPPRIMEES" -gt 0 ] && echo "  rotation : ${SUPPRIMEES} archive(s) de plus de ${RETENTION_JOURS} jours supprimee(s)"

RESTANTES=$(find "$DESTINATION" -maxdepth 1 -name 'sirh_*.tar.gz' | wc -l)
echo "[$(date '+%F %T')] Termine — ${RESTANTES} sauvegarde(s) conservee(s)"
