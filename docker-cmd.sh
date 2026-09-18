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

# --- Mot de passe maitre ---------------------------------------------------
# Coolify (comme tout deploiement depuis un depot git) ne dispose que des
# fichiers versionnes : un odoo.conf contenant un secret ne peut donc pas
# exister sur le serveur. Quand ODOO_ADMIN_PASSWD est fourni, on rend une
# configuration a partir du modele et on la passe explicitement a Odoo.
# Sans cette variable, rien ne change : Odoo lit /etc/odoo/odoo.conf comme
# avant, ce qui preserve le fonctionnement du poste de developpement.
CONF_ARGS=()
MODELE_CONF="${ODOO_CONF_TEMPLATE:-/etc/odoo/odoo.conf}"
if [ -n "${ODOO_ADMIN_PASSWD:-}" ] && [ -f "$MODELE_CONF" ]; then
    CONF_RENDU=/tmp/odoo.rendu.conf
    sed "s|^admin_passwd *=.*|admin_passwd = ${ODOO_ADMIN_PASSWD}|" \
        "$MODELE_CONF" > "$CONF_RENDU"
    chmod 600 "$CONF_RENDU"
    if grep -qE '^admin_passwd = (REMPLACER_AVANT_DEMARRAGE|cosmic_admin|admin|)$' "$CONF_RENDU"; then
        echo "ECHEC : le mot de passe maitre n'a pas ete injecte." >&2
        exit 1
    fi
    CONF_ARGS=(-c "$CONF_RENDU")
    echo "Configuration rendue depuis ${MODELE_CONF} (mot de passe maitre injecte)."
fi

# N'installe/n'initialise "base" que si la base cible n'a pas encore de
# schema Odoo (verifie via la presence de la table ir_module_module) :
# rejouer les donnees de base/data/*.xml sur une base deja peuplee peut
# echouer sur des contraintes ajoutees depuis par d'autres modules -
# verifie concretement : plante sur "res_users_notification_type" en local
# (base SIRH deja installee avec les modules RH tiers). Sans cette
# verification, -i base casserait le demarrage local a chaque redemarrage.
IS_INITIALIZED=$(PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -tAc \
    "SELECT to_regclass('public.ir_module_module') IS NOT NULL" 2>/dev/null || echo "f")

# Liste exacte des modules installes en local (SIRH), relevee le 18/09/2026.
# Une liste perimee ne se voit pas : l'instance neuve demarre normalement,
# simplement amputee des modules manquants. Au 18/09 il en manquait 42,
# dont villa_nova_localisation et villa_nova_project. Ancien commentaire -
# `env['ir.module.module'].search([('state','=','installed')])` pour la
# regenerer si de nouveaux modules sont installes localement par la suite.
# --without-demo=all : logiciel complet installe (tous les modules, donc
# tous les ecrans/fonctionnalites), mais aucune donnee d'entreprise reelle
# (pas d'employe, pas de candidat, pas de presence) - juste les donnees de
# reference que chaque module installe lui-meme (etapes, groupes, gabarits).
ALL_MODULES="account,account_add_gln,account_edi_ubl_cii,account_payment,analytic,attachment_indexation,auth_signup,auth_totp,auth_totp_mail,auth_totp_portal,barcodes,barcodes_gs1_nomenclature,base,base_automation,base_import,base_import_module,base_install_request,base_setup,bus,calendar,calendar_sms,contacts,crm,crm_iap_enrich,crm_iap_mine,crm_sms,digest,event,event_crm,event_product,event_sms,gamification,google_gmail,google_recaptcha,hr,hr_attendance,hr_biometric_attendance,hr_calendar,hr_contract,hr_employee_transfer,hr_employee_updation,hr_expense,hr_gamification,hr_holidays,hr_holidays_attendance,hr_holidays_contract,hr_hourly_cost,hr_insurance,hr_leave_request_aliasing,hr_maintenance,hr_multi_company,hr_org_chart,hr_payroll_account_community,hr_payroll_community,hr_recruitment,hr_recruitment_skills,hr_recruitment_sms,hr_recruitment_survey,hr_reminder,hr_resignation,hr_reward_warning,hr_skills,hr_skills_slides,hr_skills_survey,hr_timesheet,hr_timesheet_attendance,hrms_dashboard,html_editor,http_routing,iap,iap_crm,iap_mail,l10n_ci,l10n_syscohada,link_tracker,mail,mail_bot,mail_bot_hr,maintenance,mass_mailing,mass_mailing_crm,mass_mailing_event,mass_mailing_slides,mass_mailing_themes,microsoft_outlook,oh_appraisal,oh_employee_creation_from_user,oh_employee_documents_expiry,ohrms_core,ohrms_loan,ohrms_loan_accounting,ohrms_salary_advance,ohrms_service_request,onboarding,partner_autocomplete,payment,phone_validation,portal,portal_rating,privacy_lookup,product,project,project_account,project_hr_expense,project_hr_skills,project_purchase,project_purchase_stock,project_sms,project_stock,project_stock_account,project_timesheet_holidays,project_todo,purchase,purchase_edi_ubl_bis3,purchase_stock,rating,resource,resource_mail,sales_team,sms,snailmail,snailmail_account,social_media,spreadsheet,spreadsheet_account,spreadsheet_dashboard,spreadsheet_dashboard_account,spreadsheet_dashboard_hr_timesheet,spreadsheet_dashboard_stock_account,stock,stock_account,stock_sms,survey,uom,utm,villa_nova_analytics,villa_nova_appraisal,villa_nova_biometric_attendance,villa_nova_change,villa_nova_cmdb,villa_nova_contracts,villa_nova_dashboard,villa_nova_elearning,villa_nova_endpoint,villa_nova_itam,villa_nova_itsm,villa_nova_knowledge,villa_nova_leaves,villa_nova_localisation,villa_nova_onboarding,villa_nova_portal,villa_nova_project,villa_nova_recruitment,villa_nova_settings,villa_nova_shell,villa_nova_theme,villa_nova_timesheets,web,web_editor,web_hierarchy,web_tour,web_unsplash,website,website_crm,website_crm_sms,website_hr_recruitment,website_links,website_mail,website_mass_mailing,website_partner,website_payment,website_profile,website_project,website_slides,website_slides_survey,website_sms"

# --max-cron-threads=0 pendant l'installation initiale UNIQUEMENT.
#
# Les taches planifiees demarrent en parallele de l'installation et ecrivent
# dans ir_cron, pendant que l'installation des modules y ecrit aussi. Les deux
# se bloquent :
#     psycopg2.errors.LockNotAvailable: could not obtain lock on ir_cron
#     ParseError: while parsing base/data/ir_cron_data.xml
#     Failed to load registry
# Constate le 18/09/2026 sur le VPS : l'installation s'est arretee a 156
# modules sur 176, laissant de cote villa_nova_localisation et
# villa_nova_project. Invisible en local, ou la base est deja installee.
#
# Au demarrage suivant, la valeur de odoo.prod.conf (max_cron_threads = 2)
# reprend : les taches planifiees fonctionnent normalement en exploitation.
#
# Base neuve : on installe TOUTE la liste, pas le seul module "base" - sinon
# l'instance demarre sur un Odoo nu, sans aucun ecran RH.
if [ "$IS_INITIALIZED" = "t" ]; then
    exec odoo "${CONF_ARGS[@]}" --db_host="$DB_HOST" --db_port="$DB_PORT" --db_user="$DB_USER" --db_password="$DB_PASSWORD" --http-port="$HTTP_PORT" -d "$DB_NAME" \
        --addons-path=/usr/lib/python3/dist-packages/odoo/addons,/mnt/extra-addons
else
    exec odoo "${CONF_ARGS[@]}" --db_host="$DB_HOST" --db_port="$DB_PORT" --db_user="$DB_USER" --db_password="$DB_PASSWORD" --http-port="$HTTP_PORT" -d "$DB_NAME" -i "$ALL_MODULES" --without-demo=all --max-cron-threads=0 \
        --addons-path=/usr/lib/python3/dist-packages/odoo/addons,/mnt/extra-addons
fi