# Les employes reels de ce SIRH sont crees via l'UI/import RH et n'ont pas
# d'ID externe exploitable en donnees XML statiques - meme rattrapage que les
# membres d'equipe ITSM (villa_nova_itsm/hooks.py). Ne s'applique qu'en
# presence des donnees de demo (env.ref renvoie None sinon, sans erreur).

ASSET_EMPLOYEE_LOGINS = {
    'villa_nova_itam.demo_asset_laptop_elishama': 'elishama.brou@infinity-africa.com',
    'villa_nova_itam.demo_asset_laptop_abdoulaye': 'abdoulaye.meite@infinity-africa.com',
    'villa_nova_itam.demo_asset_laptop_dell': 'ismael.cisse@infinity-africa.com',
    'villa_nova_itam.demo_asset_desktop_hr': 'joelle.bah@infinity-africa.com',
    'villa_nova_itam.demo_asset_mobile': 'koumba.assanvo@infinity-africa.com',
}

# Adobe est volontairement sur-alloue (3 sieges achetes, 4 attributions) pour
# demontrer le badge de non-conformite des la demo.
SOFTWARE_ASSIGNMENT_LOGINS = {
    'villa_nova_itam.demo_license_adobe': [
        'angecedric.seyouo@infinity-africa.com',
        'bertrand.aman@infinity-africa.com',
        'rodolphe.ibo@infinity-africa.com',
        'audrey.bailly@infinity-africa.com',
    ],
    'villa_nova_itam.demo_license_github': [
        'abdoulaye.meite@infinity-africa.com',
        'elishama.brou@infinity-africa.com',
        'fadel.koloma@infinity-africa.com',
        'mederic.gbagba@infinity-africa.com',
    ],
    'villa_nova_itam.demo_license_m365': [
        'abdoulaye.meite@infinity-africa.com',
        'elishama.brou@infinity-africa.com',
        'ismael.cisse@infinity-africa.com',
        'joelle.bah@infinity-africa.com',
        'koumba.assanvo@infinity-africa.com',
    ],
}


def _employee_by_login(env, login):
    return env['hr.employee'].search([('user_id.login', '=', login)], limit=1)


def _seed_demo_asset_employees(env):
    for asset_xmlid, login in ASSET_EMPLOYEE_LOGINS.items():
        asset = env.ref(asset_xmlid, raise_if_not_found=False)
        employee = _employee_by_login(env, login)
        if asset and employee:
            asset.write({'employee_id': employee.id})


def _seed_demo_software_assignments(env):
    Assignment = env['itam.software.assignment']
    for license_xmlid, logins in SOFTWARE_ASSIGNMENT_LOGINS.items():
        license = env.ref(license_xmlid, raise_if_not_found=False)
        if not license:
            continue
        for login in logins:
            employee = _employee_by_login(env, login)
            if not employee:
                continue
            if Assignment.search([
                ('license_id', '=', license.id), ('employee_id', '=', employee.id),
            ], limit=1):
                continue
            Assignment.create({'license_id': license.id, 'employee_id': employee.id})


def post_init(env):
    _seed_demo_asset_employees(env)
    _seed_demo_software_assignments(env)
