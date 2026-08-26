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

# Liste exacte des modules installes en local (SIRH) au 26/08/2026 - relever
# `env['ir.module.module'].search([('state','=','installed')])` pour la
# regenerer si de nouveaux modules sont installes localement par la suite.
# --without-demo=all : logiciel complet installe (tous les modules, donc
# tous les ecrans/fonctionnalites), mais aucune donnee d'entreprise reelle
# (pas d'employe, pas de candidat, pas de presence) - juste les donnees de
# reference que chaque module installe lui-meme (etapes, groupes, gabarits).
ALL_MODULES="account,account_add_gln,account_edi_ubl_cii,account_payment,analytic,attachment_indexation,auth_signup,auth_totp,auth_totp_mail,auth_totp_portal,barcodes,barcodes_gs1_nomenclature,base,base_automation,base_import,base_import_module,base_install_request,base_setup,bus,calendar,calendar_sms,digest,event,event_product,event_sms,gamification,google_gmail,google_recaptcha,hr,hr_attendance,hr_biometric_attendance,hr_calendar,hr_contract,hr_employee_transfer,hr_employee_updation,hr_expense,hr_gamification,hr_holidays,hr_holidays_attendance,hr_holidays_contract,hr_hourly_cost,hr_insurance,hr_leave_request_aliasing,hr_multi_company,hr_org_chart,hr_payroll_account_community,hr_payroll_community,hr_recruitment,hr_recruitment_skills,hr_recruitment_sms,hr_recruitment_survey,hr_reminder,hr_resignation,hr_reward_warning,hr_skills,hr_skills_survey,hr_timesheet,hr_timesheet_attendance,hrms_dashboard,html_editor,http_routing,iap,iap_mail,l10n_ci,l10n_syscohada,mail,mail_bot,mail_bot_hr,microsoft_outlook,oh_appraisal,oh_employee_creation_from_user,oh_employee_documents_expiry,ohrms_core,ohrms_loan,ohrms_loan_accounting,ohrms_salary_advance,ohrms_service_request,onboarding,partner_autocomplete,payment,phone_validation,portal,portal_rating,privacy_lookup,product,project,project_account,project_hr_expense,project_hr_skills,project_sms,project_stock,project_stock_account,project_timesheet_holidays,project_todo,rating,resource,resource_mail,sms,snailmail,snailmail_account,social_media,spreadsheet,spreadsheet_account,spreadsheet_dashboard,spreadsheet_dashboard_account,spreadsheet_dashboard_hr_timesheet,spreadsheet_dashboard_stock_account,stock,stock_account,stock_sms,survey,uom,utm,villa_nova_appraisal,villa_nova_biometric_attendance,villa_nova_dashboard,villa_nova_leaves,villa_nova_onboarding,villa_nova_recruitment,villa_nova_settings,villa_nova_shell,villa_nova_theme,villa_nova_timesheets,web,web_editor,web_hierarchy,web_tour,web_unsplash,website,website_hr_recruitment,website_mail,website_payment,website_project,website_sms"

if [ "$IS_INITIALIZED" = "t" ]; then
    exec odoo --db_host="$DB_HOST" --db_port="$DB_PORT" --db_user="$DB_USER" --db_password="$DB_PASSWORD" --http-port="$HTTP_PORT" -d "$DB_NAME" \
        --addons-path=/usr/lib/python3/dist-packages/odoo/addons,/mnt/extra-addons
else
    exec odoo --db_host="$DB_HOST" --db_port="$DB_PORT" --db_user="$DB_USER" --db_password="$DB_PASSWORD" --http-port="$HTTP_PORT" -d "$DB_NAME" -i base --without-demo=all \
        --addons-path=/usr/lib/python3/dist-packages/odoo/addons,/mnt/extra-addons
fi