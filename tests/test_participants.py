from dataclasses import FrozenInstanceError, replace
import json
import unittest

from domain_events import CommonEventLog
from marker_tracking import MarkerObservation, MarkerTracker, ObservationFrame
from participants import ParticipantBinding, ParticipantRegistry


def binding(pid='p1', marker=0, source='camera:0', name='Júlia', color='#48b8e8'):
    return ParticipantBinding(pid, name, color, source, marker)


class ParticipantRegistryTests(unittest.TestCase):
    def test_identity_is_independent_of_marker_name_and_source(self):
        registry = ParticipantRegistry([binding(), binding('p2', source='camera:1')])
        old = registry.snapshot()
        registry.upsert(binding(marker=4, name='Júlia nova', color='#FF0000'))
        self.assertEqual(old['p1'].marker_id, 0)
        self.assertEqual(registry.snapshot()['p1'].participant_id, 'p1')
        self.assertIsNone(registry.participant_for('camera:0', 0))
        self.assertEqual(registry.participant_for('camera:0', 4).name, 'Júlia nova')
        self.assertEqual(registry.participant_for('camera:1', 0).participant_id, 'p2')
        with self.assertRaises(TypeError):
            old['x'] = binding()
        with self.assertRaises(FrozenInstanceError):
            old['p1'].name = 'Canvi'

    def test_duplicate_binding_is_rejected_atomically_including_retired(self):
        registry = ParticipantRegistry([binding(), binding('p2', 1)])
        registry.set_retired('p1')
        before = registry.to_dict()
        for p in (binding('p3'), binding('p2', 0)):
            with self.assertRaisesRegex(ValueError, 'assignats'):
                registry.upsert(p)
            self.assertEqual(registry.to_dict(), before)
        registry.remove('p1')
        registry.upsert(binding('p2', 0))
        self.assertEqual(len(registry.snapshot()), 1)

    def test_invalid_fields_and_colors_are_rejected(self):
        original = binding()
        for changes in ({'participant_id': ''}, {'participant_id': True}, {'source_id': ' '},
                        {'name': 'a' * 81}, {'name': 'line\nbreak'}, {'name': None},
                        {'color': 'red'}, {'color': '#12345G'}, {'color': None},
                        {'marker_id': True}, {'marker_id': '0'}, {'marker_id': -1}, {'marker_id': 16}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(original, **changes)
        self.assertEqual(original.color, '#48B8E8')
        self.assertEqual(binding(name='').name, '')

    def test_roundtrip_keeps_configuration_only_and_old_projects_stay_empty(self):
        registry = ParticipantRegistry([binding(), binding('p2', 1)])
        registry.set_retired('p1')
        encoded = json.loads(json.dumps({'version': 4, 'participants': registry.to_dict()}))
        loaded = ParticipantRegistry.from_project(encoded)
        self.assertEqual(loaded.to_dict(), registry.to_dict())
        self.assertEqual(loaded.states({})['p1'].presence, 'not_seen')
        self.assertNotIn('retired', json.dumps(encoded))
        self.assertEqual(len(ParticipantRegistry.from_project({'cards': [{'name': 'Not a person'}]}).snapshot()), 0)

    def test_invalid_schema_duplicate_ids_and_duplicate_markers_are_rejected(self):
        good = {'schema_version': 1, 'bindings': [binding().to_dict()]}
        for block in (None, [], {}, dict(good, schema_version=True), dict(good, schema_version=2),
                      dict(good, bindings='bad'), dict(good, bindings=[{}]),
                      dict(good, bindings=[binding().to_dict()] * 2),
                      dict(good, bindings=[binding().to_dict(), binding('p2').to_dict()])):
            with self.subTest(block=block), self.assertRaises(ValueError):
                ParticipantRegistry.from_project({'participants': block})

    def test_registry_is_bounded(self):
        registry = ParticipantRegistry(binding(str(i), i % 16, f'camera:{i // 16}') for i in range(64))
        with self.assertRaises(ValueError):
            registry.upsert(binding('overflow', source='camera:4'))
        registry.upsert(binding('0', color='#000000'))
        self.assertEqual(len(registry.snapshot()), 64)

    def test_loss_outage_and_retirement_never_delete_person_or_reassign_marker(self):
        registry = ParticipantRegistry([binding()])
        tracker = MarkerTracker()
        observation = MarkerObservation(0, (.2, .3), .5)
        tracker.update(ObservationFrame('camera:0', 1, 1, (observation,)))
        self.assertTrue(registry.states(tracker.snapshot())['p1'].observed)
        tracker.update(ObservationFrame('camera:0', 2, 1.1))
        lost = registry.states(tracker.snapshot())['p1']
        self.assertEqual(lost.presence, 'temporarily_lost')
        self.assertFalse(lost.observed)
        self.assertEqual(lost.marker_state.last_observation.position, (.2, .3))
        tracker.update(ObservationFrame('camera:0', 3, 50, status='unavailable'))
        self.assertEqual(registry.states(tracker.snapshot())['p1'].presence, 'temporarily_lost')
        registry.set_retired('p1')
        tracker.update(ObservationFrame('camera:0', 4, 51, (observation,)))
        self.assertEqual(registry.states(tracker.snapshot())['p1'].presence, 'retired')
        self.assertFalse(registry.states(tracker.snapshot())['p1'].observed)
        self.assertTrue(tracker.snapshot()['camera:0', 0].observed)
        registry.set_retired('p1', False)
        self.assertEqual(registry.states(tracker.snapshot())['p1'].presence, 'detected')
        self.assertEqual(registry.snapshot()['p1'], binding())


class CommonEventTests(unittest.TestCase):
    def setUp(self):
        self.registry = ParticipantRegistry(binding(f'p{i}', i) for i in range(5))
        self.tracker = MarkerTracker()
        self.log = CommonEventLog()

    def update(self, sequence, now, ids=(), status='ok', source='camera:0'):
        frame = ObservationFrame(source, sequence, now, tuple(MarkerObservation(i, (.1 * i, .2), 0) for i in ids), status)
        return self.log.consume(frame, self.tracker.update(frame), self.registry)

    def test_five_people_ordering_return_loss_and_source_incidence(self):
        events = self.update(1, 1, [4, 2, 0, 3, 1])
        self.assertEqual([e.kind for e in events], ['source_available'] + ['marker_appeared'] * 5)
        self.assertEqual([e.participant_id for e in events[1:]], ['p0', 'p1', 'p2', 'p3', 'p4'])
        self.assertFalse(self.update(2, 1.1, range(5)))
        events = self.update(3, 1.2, [4, 2, 3, 1])
        self.assertEqual([(e.kind, e.participant_id) for e in events], [('marker_temporarily_lost', 'p0')])
        self.assertEqual(self.update(4, 1.3, range(5))[0].kind, 'marker_recovered')
        self.update(5, 1.4)
        events = self.update(6, 100, status='unavailable')
        self.assertEqual([e.kind for e in events], ['source_unavailable'])
        self.assertFalse(self.update(7, 200, status='unavailable'))
        events = self.update(8, 201)
        self.assertEqual([e.kind for e in events], ['source_available'] + ['marker_absent'] * 5)
        self.assertFalse(self.update(9, 202))
        self.assertEqual(len(self.registry.snapshot()), 5)

    def test_source_switch_same_marker_has_separate_identity(self):
        self.update(1, 1, [0])
        events = self.update(2, 2, [0], source='camera:1')
        self.assertIsNone(events[-1].participant_id)
        self.assertEqual(self.registry.states(self.tracker.snapshot())['p0'].marker_state.source_id, 'camera:0')

    def test_invalid_frame_does_not_generate_events(self):
        self.update(1, 1, [0])
        before = self.log.snapshot()
        with self.assertRaises(ValueError):
            self.update(1, 1, [1])
        self.assertEqual(self.log.snapshot(), before)

    def test_replay_deduplication_bounded_journal_and_complete_event_batch(self):
        self.log = CommonEventLog(limit=2)
        batch = self.update(1, 1, range(5))
        self.assertEqual(len(batch), 6)
        self.assertEqual(len(self.log.snapshot()), 2)
        with self.assertRaises(FrozenInstanceError):
            batch[0].kind = 'other'
        frame = ObservationFrame('camera:0', 1, 1)
        self.assertFalse(self.log.consume(frame, self.tracker.snapshot(), self.registry))
        self.update(2, 1.1)
        self.assertGreater(self.log.snapshot()[-1].sequence, batch[-1].sequence)

    def test_explicit_retirement_is_idempotent_and_event_history_keeps_binding(self):
        appearance = self.update(1, 1, [0])[-1]
        event = self.log.participant_retirement(self.registry, 'p0', True, 1.1)
        self.assertEqual(event.kind, 'participant_retired')
        self.assertIsNone(self.log.participant_retirement(self.registry, 'p0', True, 1.2))
        self.assertFalse(self.update(2, 1.3, [0]))
        self.assertEqual(self.registry.states(self.tracker.snapshot())['p0'].presence, 'retired')
        self.registry.upsert(binding('p0', 7))
        self.assertEqual(appearance.marker_id, 0)
        self.assertEqual(appearance.participant_id, 'p0')
        self.assertEqual(self.log.participant_retirement(self.registry, 'p0', False, 1.4).kind, 'participant_restored')
        with self.assertRaises(ValueError):
            self.log.participant_retirement(self.registry, 'p0', True, float('nan'))
        self.assertEqual(self.registry.states({})['p0'].presence, 'not_seen')


if __name__ == '__main__':
    unittest.main()
