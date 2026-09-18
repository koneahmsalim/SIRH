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

ADDONS="/usr/lib/python3/dist-packages/odoo/addons,/mnt/extra-addons"
ARGS_BASE=(--db_host="$DB_HOST" --db_port="$DB_PORT" --db_user="$DB_USER"
           --db_password="$DB_PASSWORD" --addons-path="$ADDONS")

# Combien de modules de la liste ne sont pas encore installes ?
modules_manquants() {
    local liste
    liste=$(echo "$ALL_MODULES" | sed "s/,/','/g")
    PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER"         -d "$DB_NAME" -tAc         "SELECT COUNT(*) FROM ir_module_module WHERE name IN ('$liste') AND state <> 'installed';"         2>/dev/null || echo 0
}

MANQUANTS=$(modules_manquants)

# --- Phase 1 : socle et langue -------------------------------------------
# La langue francaise doit exister AVANT les modules metier. villa_nova_recruitment
# declare ses etapes en francais ; sur une base neuve Odoo repond
#     UserError: Invalid language code: fr_FR
# et interrompt toute l'installation. Constate le 18/09/2026 sur le VPS :
# arret a 156 modules sur 176. Invisible en local, ou le francais est installe
# depuis longtemps et ou cette branche ne s'execute jamais.
# La condition porte aussi sur les modules manquants : une base a moitie
# installee (installation interrompue) n'a pas forcement le francais, et c'est
# precisement ce qui fait echouer la reprise. "-i base" sur une base deja
# installee ne fait rien ; "--load-language" est sans effet si la langue est
# deja la. Rejouer cette phase est donc sans risque.
if [ "$IS_INITIALIZED" != "t" ] || [ "${MANQUANTS:-0}" -gt 0 ]; then
    echo "Socle et langue francaise."
    odoo "${CONF_ARGS[@]}" "${ARGS_BASE[@]}" -d "$DB_NAME"         -i base --without-demo=all --load-language=fr_FR         --max-cron-threads=0 --stop-after-init
fi

# --- Phase 2 : modules metier, avec reprise -------------------------------
# On interroge l'etat reel plutot que de se fier a un drapeau : si une
# installation precedente s'est interrompue, elle reprend ici au lieu de
# demarrer une instance amputee - c'est exactement ce qui s'est produit le
# 18/09, ou l'instance est restee bloquee a 156 modules sans rien signaler.
#
# --max-cron-threads=0 pendant l'installation seulement : les taches planifiees
# ecrivent dans ir_cron pendant que l'installation y ecrit aussi, et les deux se
# bloquent (LockNotAvailable sur ir_cron). Le serveur demarre ensuite avec la
# valeur de odoo.prod.conf, cron actif.
MANQUANTS=$(modules_manquants)   # relu : la phase 1 a pu en installer
if [ "${MANQUANTS:-0}" -gt 0 ]; then
    echo "Installation de ${MANQUANTS} module(s) manquant(s) sur la liste."
    odoo "${CONF_ARGS[@]}" "${ARGS_BASE[@]}" -d "$DB_NAME"         -i "$ALL_MODULES" --without-demo=all         --max-cron-threads=0 --stop-after-init
    RESTANTS=$(modules_manquants)
    if [ "${RESTANTS:-0}" -gt 0 ]; then
        echo "ATTENTION : ${RESTANTS} module(s) n'ont pas pu etre installes." >&2
    fi
fi

# --- Phase 3 : service ----------------------------------------------------
echo "Demarrage du serveur."
exec odoo "${CONF_ARGS[@]}" "${ARGS_BASE[@]}" --http-port="$HTTP_PORT" -d "$DB_NAME"
