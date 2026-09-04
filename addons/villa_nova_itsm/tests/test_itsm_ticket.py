from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestItsmTicket(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Ticket = cls.env['itsm.ticket']
        cls.team_a = cls.env['itsm.team'].create({'name': "Équipe Test A"})
        cls.team_b = cls.env['itsm.team'].create({'name': "Équipe Test B"})

        cls.agent_a = cls._create_user('agent.a@example.com', 'villa_nova_itsm.group_itsm_agent')
        cls.agent_b = cls._create_user('agent.b@example.com', 'villa_nova_itsm.group_itsm_agent')
        cls.team_a.member_ids = [(4, cls.agent_a.id)]
        cls.team_b.member_ids = [(4, cls.agent_b.id)]

        cls.sla = cls.env['itsm.sla.policy'].create({
            'name': "SLA Test",
            'line_ids': [
                (0, 0, {'priority': 'critical', 'first_response_hours': 1, 'resolution_hours': 4}),
                (0, 0, {'priority': 'medium', 'first_response_hours': 4, 'resolution_hours': 24}),
            ],
        })
        cls.team_a.default_sla_policy_id = cls.sla.id

    @classmethod
    def _create_user(cls, login, *group_xmlids):
        groups = cls.env['res.groups']
        for xmlid in group_xmlids:
            groups |= cls.env.ref(xmlid)
        return cls.env['res.users'].create({
            'name': login,
            'login': login,
            'email': login,
            'groups_id': [(6, 0, groups.ids)],
        })

    def test_ticket_sequence_and_type(self):
        ticket = self.Ticket.create({'subject': "Test incident", 'ticket_type': 'incident'})
        self.assertTrue(ticket.name.startswith('INC-'), "La référence doit être préfixée INC- pour un incident.")

        request = self.Ticket.create({'subject': "Test demande", 'ticket_type': 'service_request'})
        self.assertTrue(request.name.startswith('SR-'))

    def test_priority_matrix(self):
        ticket = self.Ticket.create({'subject': "Test priorité", 'impact': 'high', 'urgency': 'high'})
        self.assertEqual(ticket.priority, 'critical')

        ticket.write({'impact': 'low', 'urgency': 'low'})
        self.assertEqual(ticket.priority, 'low')

    def test_state_transitions(self):
        ticket = self.Ticket.create({'subject': "Test workflow"})
        self.assertEqual(ticket.state, 'new')

        ticket.action_assign_to_me()
        # action_assign_to_me tourne sous l'utilisateur courant (admin en test) ;
        # on verifie juste que l'etat a bien avance et qu'un agent est defini.
        self.assertEqual(ticket.state, 'assigned')
        self.assertTrue(ticket.user_id)

        ticket.action_start_progress()
        self.assertEqual(ticket.state, 'in_progress')

        with self.assertRaises(UserError):
            ticket.write({'state': 'new'})

        ticket.write({'state': 'resolved'})
        self.assertTrue(ticket.resolved_date)
        ticket.write({'state': 'closed'})
        self.assertTrue(ticket.closed_date)

    def test_sla_deadlines_computed(self):
        ticket = self.Ticket.create({
            'subject': "Test SLA",
            'team_id': self.team_a.id,
            'impact': 'high', 'urgency': 'high',  # -> critical
        })
        self.assertEqual(ticket.sla_policy_id, self.sla)
        self.assertTrue(ticket.sla_resolution_deadline)
        self.assertTrue(ticket.sla_resolution_deadline > ticket.create_date)

    def test_agent_sees_only_own_team_tickets(self):
        ticket_a = self.Ticket.create({'subject': "Ticket équipe A", 'team_id': self.team_a.id})
        ticket_b = self.Ticket.create({'subject': "Ticket équipe B", 'team_id': self.team_b.id})

        visible_to_a = self.Ticket.with_user(self.agent_a).search([('id', 'in', [ticket_a.id, ticket_b.id])])
        self.assertIn(ticket_a.id, visible_to_a.ids)
        self.assertNotIn(ticket_b.id, visible_to_a.ids)

    def test_merge_wizard(self):
        source = self.Ticket.create({'subject': "Doublon"})
        target = self.Ticket.create({'subject': "Ticket principal"})
        wizard = self.env['itsm.ticket.merge.wizard'].create({
            'source_ticket_id': source.id,
            'target_ticket_id': target.id,
        })
        wizard.action_confirm()
        self.assertEqual(source.merged_into_id, target)
        self.assertEqual(source.state, 'cancelled')
        self.assertFalse(source.active)
        self.assertIn(source, target.linked_ticket_ids)

    def test_resolve_wizard_sets_close_notes(self):
        ticket = self.Ticket.create({'subject': "À résoudre"})
        wizard = self.env['itsm.ticket.resolve.wizard'].create({
            'ticket_ids': [(6, 0, [ticket.id])],
            'close_notes': "<p>Résolu par redémarrage.</p>",
        })
        wizard.action_confirm()
        self.assertEqual(ticket.state, 'resolved')
        self.assertIn('redémarrage', ticket.close_notes)
