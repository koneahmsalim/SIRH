import os

new_url = os.environ.get('NEW_BASE_URL')
if not new_url:
    print('MISSING_NEW_BASE_URL')
else:
    IrConfig = env['ir.config_parameter'].sudo()
    old = IrConfig.get_param('web.base.url')
    if old != new_url:
        IrConfig.set_param('web.base.url', new_url)
        env.cr.commit()
        print(f'CHANGED {old} -> {new_url}')
    else:
        print(f'UNCHANGED {old}')
