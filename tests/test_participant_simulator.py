from dataclasses import replace
import unittest

from marker_tracking import MarkerObservation, MarkerTracker, ObservationFrame
from participant_simulator import SimulatorSession, SOURCE_ID
from participants import ParticipantBinding


class SimulatorSessionTests(unittest.TestCase):
    def setUp(self):
        self.session = SimulatorSession()

    def test_five_independent_markers_use_production_contract_and_stable_identity(self):
        session = self.session
        frame, events = session.advance(0)
        self.assertIsInstance(frame, ObservationFrame)
        self.assertEqual(frame.source_id, SOURCE_ID)
        self.assertEqual(frame.coordinate_space, 'camera_normalized')
        self.assertEqual([o.marker_id for o in frame.observations], list(range(5)))
        self.assertEqual(len(events), 6)
        self.assertEqual(len({e.participant_id for e in events[1:]}), 5)
        before = session.registry.to_dict()
        pose = session.poses()['virtual-1']
        session.set_pose('virtual-1', position=(.9, .8), orientation=.25)
        frame, events = session.advance(.1)
        self.assertFalse(events)
        states = session.registry.states(session.tracker.snapshot())
        self.assertEqual(states['virtual-1'].marker_state.last_observation.position, (.9, .8))
        self.assertEqual(states['virtual-1'].marker_state.last_observation.orientation, .25)
        self.assertEqual(session.poses()['virtual-2'].position, (.5, .25))
        self.assertEqual(pose.position, (.25, .3))
        self.assertEqual(session.registry.to_dict(), before)

    def test_hiding_individual_confirms_absence_without_deleting_or_swapping_people(self):
        s = self.session
        s.advance(1)
        s.set_pose('virtual-3', visible=False)
        _, events = s.advance(1.1)
        self.assertEqual([(e.kind, e.participant_id) for e in events], [('marker_temporarily_lost', 'virtual-3')])
        _, events = s.advance(2.1)
        self.assertEqual([(e.kind, e.participant_id) for e in events], [('marker_absent', 'virtual-3')])
        self.assertEqual(len(s.registry.snapshot()), 5)
        self.assertTrue(all(state.observed for pid, state in s.registry.states(s.tracker.snapshot()).items() if pid != 'virtual-3'))
        s.set_pose('virtual-3', visible=True)
        _, events = s.advance(2.2)
        self.assertEqual(events[0].participant_id, 'virtual-3')
        self.assertEqual(s.tracker.snapshot()[SOURCE_ID, 2].first_seen, 1)

    def test_source_outage_is_not_absence_and_recovery_keeps_all_identities(self):
        s = self.session
        s.advance(1)
        s.available = False
        frame, events = s.advance(100)
        self.assertEqual(frame.status, 'unavailable')
        self.assertEqual(frame.observations, ())
        self.assertEqual(events[0].kind, 'source_unavailable')
        self.assertTrue(all(state.presence == 'temporarily_lost' for state in s.registry.states(s.tracker.snapshot()).values()))
        self.assertFalse(s.advance(200)[1])
        s.available = True
        frame, events = s.advance(201)
        self.assertEqual(events[0].kind, 'source_available')
        self.assertTrue(all(state.observed for state in s.registry.states(s.tracker.snapshot()).values()))
        self.assertTrue(all(state.first_seen == 1 for state in s.tracker.snapshot().values()))

    def test_retirement_is_explicit_sticky_and_restorable_without_recreating_person(self):
        s = self.session
        s.advance(1)
        binding = s.registry.snapshot()['virtual-1']
        s.set_retired('virtual-1', True, 1.1)
        s.set_pose('virtual-1', visible=True)
        frame, _ = s.advance(1.2)
        self.assertNotIn(0, [o.marker_id for o in frame.observations])
        self.assertEqual(s.registry.states(s.tracker.snapshot())['virtual-1'].presence, 'retired')
        s.set_retired('virtual-1', False, 1.3)
        frame, _ = s.advance(1.4)
        self.assertIn(0, [o.marker_id for o in frame.observations])
        self.assertEqual(s.registry.snapshot()['virtual-1'], binding)

    def test_edits_rebind_same_person_and_reject_duplicate_source_or_sixth_person(self):
        s = self.session
        p = s.registry.snapshot()['virtual-1']
        for candidate in (replace(p, marker_id=1), replace(p, source_id='camera:0'),
                          ParticipantBinding('sixth', '', '#000000', SOURCE_ID, 5)):
            with self.assertRaises(ValueError):
                s.registry.upsert(candidate)
        s.registry.upsert(replace(p, marker_id=15, name='Mar', color='#FF0000'))
        frame, _ = s.advance(1)
        self.assertIn(15, [o.marker_id for o in frame.observations])
        self.assertEqual(s.registry.participant_for(SOURCE_ID, 15).participant_id, 'virtual-1')
        s.registry.remove('virtual-1')
        s.registry.upsert(ParticipantBinding('new-person', 'Nou', '#ABCDEF', SOURCE_ID, 0))
        self.assertNotIn('virtual-1', s.poses())
        self.assertIn('new-person', s.poses())

    def test_invalid_pose_or_time_is_rejected_without_partial_tracking(self):
        s = self.session
        s.advance(1)
        before = s.poses()
        for changes in ({'position': (-.1, .5)}, {'position': (float('nan'), .5)},
                        {'orientation': 1}, {'orientation': float('inf')}, {'visible': 'false'}):
            with self.assertRaises(ValueError):
                s.set_pose('virtual-1', **changes)
            self.assertEqual(s.poses(), before)
        tracked = s.tracker.snapshot()
        events = s.events.snapshot()
        for now in (1, 0, float('nan'), float('inf'), True):
            with self.assertRaises(ValueError):
                s.advance(now)
            self.assertEqual(s.tracker.snapshot(), tracked)
            self.assertEqual(s.events.snapshot(), events)
            self.assertEqual(s.sequence, 1)

    def test_simulated_and_equivalent_camera_frames_have_same_tracking_semantics(self):
        camera = MarkerTracker()
        for sequence, now in enumerate((1, 1.1, 2.2, 2.3), 1):
            self.session.set_pose('virtual-1', visible=sequence in (1, 4))
            frame, _ = self.session.advance(now)
            physical = ObservationFrame('camera:0', sequence, now, frame.observations, frame.status)
            camera.update(physical)
            for marker in range(5):
                a = camera.snapshot()['camera:0', marker]
                b = self.session.tracker.snapshot()[SOURCE_ID, marker]
                self.assertEqual((a.presence, a.observed, a.history, a.last_observation),
                                 (b.presence, b.observed, b.history, b.last_observation))

    def test_history_and_events_remain_bounded_and_sessions_do_not_share_state(self):
        s = self.session
        other = SimulatorSession()
        for i in range(600):
            s.set_pose('virtual-1', visible=i % 2 == 0)
            s.advance(i*.1)
        self.assertLessEqual(len(s.events.snapshot()), 500)
        self.assertTrue(all(len(state.history) <= 90 for state in s.tracker.snapshot().values()))
        self.assertFalse(other.tracker.snapshot())
        self.assertFalse(other.events.snapshot())
        self.assertTrue(other.poses()['virtual-1'].visible)

    def test_reset_clears_runtime_and_bindings_for_a_new_virtual_session(self):
        s = self.session
        s.advance(1)
        s.set_retired('virtual-1', True, 1.1)
        s.registry.remove('virtual-2')
        s.available = False
        s.reset()
        self.assertEqual(len(s.registry.snapshot()), 5)
        self.assertFalse(s.tracker.snapshot())
        self.assertFalse(s.events.snapshot())
        self.assertEqual(s.sequence, 0)
        self.assertTrue(s.available)
        self.assertTrue(all(state.presence == 'not_seen' for state in s.registry.states({}).values()))


if __name__ == '__main__':
    unittest.main()
