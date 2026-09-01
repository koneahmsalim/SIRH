from odoo import fields, models


class HrAttendance(models.Model):
    """Ajoute une valeur "Boitier biometrique" a in_mode/out_mode (natifs
    hr_attendance : kiosk/systray/manual/technical) - sans elle, les pointages
    du boitier tombaient par defaut sur "manual", indiscernables d'une vraie
    saisie manuelle RH dans les filtres/rapports natifs."""
    _inherit = 'hr.attendance'

    in_mode = fields.Selection(
        selection_add=[('badge', "Boîtier biométrique")],
        ondelete={'badge': 'set default'},
    )
    out_mode = fields.Selection(
        selection_add=[('badge', "Boîtier biométrique")],
        ondelete={'badge': 'set default'},
    )
