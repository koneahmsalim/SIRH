from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

CI_MODEL_SELECTION = [
    ('maintenance.equipment', "Actif matériel"),
    ('itsm.service', "Service"),
]

RELATION_TYPE_SELECTION = [
    ('depends_on', "Dépend de"),
    ('hosted_on', "Hébergé sur"),
    ('connects_to', "Connecté à"),
    ('part_of', "Fait partie de"),
]

# Types de relation qui propagent une panne du sujet (target) vers celui qui
# le referme (source) - utilises pour l'analyse d'impact. "part_of" est
# volontairement exclu : qu'un CI fasse partie d'un ensemble ne veut pas
# dire qu'il tombe si l'ensemble change.
IMPACT_RELATION_TYPES = ('depends_on', 'hosted_on', 'connects_to')

IMPACT_MAX_DEPTH = 3


class CmdbRelation(models.Model):
    _name = 'cmdb.relation'
    _description = "Relation CMDB entre éléments de configuration"
    _order = 'id desc'
    _rec_name = 'display_name'

    source_ref = fields.Reference(CI_MODEL_SELECTION, string="Source", required=True, index=True)
    relation_type = fields.Selection(RELATION_TYPE_SELECTION, string="Relation", required=True)
    target_ref = fields.Reference(CI_MODEL_SELECTION, string="Cible", required=True, index=True)
    display_name = fields.Char(compute='_compute_display_name')
    notes = fields.Char(string="Notes")

    @api.depends('source_ref', 'relation_type', 'target_ref')
    def _compute_display_name(self):
        relation_labels = dict(RELATION_TYPE_SELECTION)
        for relation in self:
            source_name = relation.source_ref.display_name if relation.source_ref else '?'
            target_name = relation.target_ref.display_name if relation.target_ref else '?'
            label = relation_labels.get(relation.relation_type, relation.relation_type or '')
            relation.display_name = "%s → %s → %s" % (source_name, label, target_name)

    @api.constrains('source_ref', 'target_ref')
    def _check_not_self_referencing(self):
        for relation in self:
            if relation.source_ref and relation.target_ref and relation.source_ref == relation.target_ref:
                raise ValidationError(_("Un CI ne peut pas être en relation avec lui-même."))

    _sql_constraints = [
        ('no_duplicate_relation', 'unique (source_ref, relation_type, target_ref)',
         "Cette relation existe déjà entre ces deux éléments de configuration."),
    ]

    @api.model
    def _impact_analysis(self, root_ref, max_depth=IMPACT_MAX_DEPTH):
        """Si le CI 'root_ref' (chaine 'model,id') tombe en panne, quels
        sont les CI impactes - directement, puis transitivement jusqu'a
        max_depth. Un CI source d'une relation depends_on/hosted_on/
        connects_to dont la cible est dans le perimetre courant est
        impacte, et rejoint a son tour le perimetre pour le niveau suivant."""
        visited_refs = {root_ref}
        impacted_equipment = self.env['maintenance.equipment'].browse()
        impacted_services = self.env['itsm.service'].browse()
        frontier = {root_ref}
        for _level in range(max_depth):
            if not frontier:
                break
            relations = self.search([
                ('target_ref', 'in', list(frontier)),
                ('relation_type', 'in', list(IMPACT_RELATION_TYPES)),
            ])
            frontier = set()
            for relation in relations:
                source = relation.source_ref
                if not source:
                    continue
                ref = '%s,%s' % (source._name, source.id)
                if ref in visited_refs:
                    continue
                visited_refs.add(ref)
                frontier.add(ref)
                if source._name == 'maintenance.equipment':
                    impacted_equipment |= source
                else:
                    impacted_services |= source
        return impacted_equipment, impacted_services
