#!/bin/bash
set -e

# db_port fixe a 5432 volontairement : sur Render, $PORT designe le port
# HTTP public du service (routage), qui entre en collision avec l'usage
# interne de $PORT par l'entrypoint officiel Odoo (repli pour db_port).
DB_HOST="${HOST:-postgres}"
DB_PORT=5432
DB_USER="${USER:-odoo}"
DB_PASSWORD="${PASSWORD:-odoo}"
DB_NAME="${DBNAME:-SIRH}"
HTTP_PORT="${PORT:-8069}"

# N'installe/n'initialise "base" que si la base cible n'a pas encore de
# schema Odoo (verifie via la presence de la table ir_module_module) :
# rejouer les donnees de base/data/*.xml sur une base deja peuplee peut
# echouer sur des contraintes ajoutees depuis par d'autres modules -
# verifie concretement : plante sur "res_users_notification_type" en local
# (base SIRH deja installee avec les modules RH tiers). Sans cette
# verification, -i base casserait le demarrage local a chaque redemarrage.
IS_INITIALIZED=$(PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -tAc \
    "SELECT to_regclass('public.ir_module_module') IS NOT NULL" 2>/dev/null || echo "f")

if [ "$IS_INITIALIZED" = "t" ]; then
    exec odoo --db_host="$DB_HOST" --db_port="$DB_PORT" --db_user="$DB_USER" --db_password="$DB_PASSWORD" --http-port="$HTTP_PORT" -d "$DB_NAME"
else
    exec odoo --db_host="$DB_HOST" --db_port="$DB_PORT" --db_user="$DB_USER" --db_password="$DB_PASSWORD" --http-port="$HTTP_PORT" -d "$DB_NAME" -i base --without-demo=all
fi
