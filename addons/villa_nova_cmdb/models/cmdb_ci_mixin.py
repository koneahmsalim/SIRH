from odoo import _, fields, models

OPEN_TICKET_STATES = ('new', 'assigned', 'in_progress', 'pending')


class CmdbCiMixin(models.AbstractModel):
    """Logique CMDB partagee entre les differents types de CI (actif
    materiel, service...) - evite de dupliquer le calcul de relations et
    l'analyse d'impact dans chaque modele qui joue le role de CI."""
    _name = 'cmdb.ci.mixin'
    _description = "CI CMDB (comportement partagé)"

    cmdb_relation_count = fields.Integer(string="Relations CMDB", compute='_compute_cmdb_relation_count')

    def _cmdb_ref(self):
        self.ensure_one()
        return '%s,%s' % (self._name, self.id)

    def _compute_cmdb_relation_count(self):
        Relation = self.env['cmdb.relation']
        for record in self:
            ref = record._cmdb_ref()
            record.cmdb_relation_count = Relation.search_count(
                ['|', ('source_ref', '=', ref), ('target_ref', '=', ref)])

    def action_view_cmdb_relations(self):
        self.ensure_one()
        ref = self._cmdb_ref()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Relations CMDB"),
            'res_model': 'cmdb.relation',
            'view_mode': 'list,form',
            'domain': ['|', ('source_ref', '=', ref), ('target_ref', '=', ref)],
            'context': {'default_source_ref': ref},
        }

    def action_cmdb_impact_analysis(self):
        self.ensure_one()
        ref = self._cmdb_ref()
        impacted_equipment, impacted_services = self.env['cmdb.relation']._impact_analysis(ref)

        if not impacted_equipment and not impacted_services:
            html = _("<p>Aucun autre élément de configuration ne dépend de <b>%(name)s</b> "
                      "dans le CMDB.</p>", name=self.display_name)
        else:
            rows = []
            for equipment in impacted_equipment:
                open_count = len(equipment.ticket_ids.filtered(lambda t: t.state in OPEN_TICKET_STATES))
                extra = _(" — %(count)d ticket(s) ouvert(s)", count=open_count) if open_count else ""
                rows.append("<li><b>%s</b> (%s)%s</li>" % (
                    equipment.display_name, _("Actif matériel"), extra))
            for service in impacted_services:
                rows.append("<li><b>%s</b> (%s)</li>" % (service.display_name, _("Service")))
            html = _(
                "<p>Si <b>%(name)s</b> tombe en panne, %(count)d élément(s) de configuration "
                "seraient potentiellement impactés :</p><ul>%(rows)s</ul>",
                name=self.display_name, count=len(impacted_equipment) + len(impacted_services),
                rows=''.join(rows),
            )

        wizard = self.env['cmdb.impact.analysis.wizard'].create({
            'ci_name': self.display_name,
            'result_html': html,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _("Analyse d'impact"),
            'res_model': 'cmdb.impact.analysis.wizard',
            'view_mode': 'form',
            'res_id': wizard.id,
            'target': 'new',
        }
