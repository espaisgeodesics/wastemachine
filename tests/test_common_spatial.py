from dataclasses import FrozenInstanceError, replace
import unittest

from common_spatial import CommonSpatialObserver
from domain_events import CommonEventLog
from marker_tracking import MarkerObservation, ObservationFrame
from participant_simulator import SimulatorSession
from participants import ParticipantBinding, ParticipantRegistry
from spatial_zones import Calibration, SpatialEngine, SpatialMap, Zone


IDENTITY = Calibration(((.5, 0), (1, .5), (.5, 1), (0, .5)))
POINTS = ((.3, .3), (.55, .3), (.7, .45), (.35, .7), (.65, .7))


def config(calibration=IDENTITY):
    cells = ((2, 2), (2, 4), (3, 5), (5, 2), (5, 5))
    return SpatialMap(zones=tuple(Zone(f'z{i}', f'Zona {i+1}', {cell}, {i}, f'{i}.png')
                                  for i, cell in enumerate(cells)), calibration=calibration)


def frame(sequence, now, points=None, source='camera:0', status='ok'):
    points = dict(enumerate(POINTS)) if points is None else points
    return ObservationFrame(source, sequence, now,
                            tuple(MarkerObservation(i, point, 0) for i, point in points.items()), status)


class CommonSpatialTests(unittest.TestCase):
    def setUp(self):
        self.observer = CommonSpatialObserver(config())

    def confirm(self, source='camera:0'):
        events = []
        for seq, now in enumerate((0, .08, .16), 1):
            events.extend(self.observer.update(frame(seq, now, source=source)))
        return events

    def test_all_five_zone_events_survive_single_winning_scene_arbitration(self):
        events = self.confirm()
        self.assertEqual([(e.kind, e.card_id, e.zone_id) for e in events],
                         [('enter', i, f'z{i}') for i in range(5)])
        for i in range(5):
            state = self.observer.snapshot()['camera:0', i]
            self.assertEqual(state.zone_id, f'z{i}')
            self.assertTrue(state.observed)
            self.assertTrue(state.calibrated)
        self.assertFalse(self.observer.update(frame(4, .24)))

    def test_exact_spatial_engine_parity_authorizations_hysteresis_and_exit_delay(self):
        engine = SpatialEngine(config())
        samples = [(0, {0: (.3, .3), 1: (.3, .3)}), (.08, {0: (.3, .3), 1: (.3, .3)}),
                   (.16, {0: (.3, .3), 1: (.3, .3)}), (.24, {0: (.38, .3)}),
                   (.32, {0: (.4, .3)}), (.4, {0: (.4, .3)}), (.54, {0: (.4, .3)}),
                   (.62, {0: (.3, .3)}), (.70, {0: (.3, .3)}), (.78, {0: (.3, .3)})]
        actual = []
        for seq, (now, points) in enumerate(samples, 1):
            expected = engine.update_camera(points, now)
            batch = self.observer.update(frame(seq, now, points))
            self.assertEqual(batch, expected.events)
            actual.extend(batch)
        self.assertEqual([(e.kind, e.card_id) for e in actual], [('enter', 0), ('exit', 0), ('enter', 0)])
        self.assertIsNone(self.observer.snapshot()['camera:0', 1].zone_id)

    def test_calibration_required_and_nonidentity_transform_reused_exactly(self):
        observer = CommonSpatialObserver(config(None))
        for seq, now in enumerate((0, .08, .16), 1):
            self.assertFalse(observer.update(frame(seq, now)))
        self.assertFalse(observer.snapshot()['camera:0', 0].calibrated)
        self.assertIsNone(observer.snapshot()['camera:0', 0].floor_position)
        shifted = Calibration(((.5, .1), (.9, .5), (.5, .9), (.1, .5)))
        observer.configure(config(shifted))
        point = shifted.unproject(POINTS[0])
        for seq, now in enumerate((1, 1.08, 1.16), 1):
            events = observer.update(frame(seq, now, {0: point}))
        self.assertEqual(events[0].zone_id, 'z0')
        for actual, expected in zip(observer.snapshot()['camera:0', 0].floor_position, POINTS[0]):
            self.assertAlmostEqual(actual, expected)

    def test_unavailable_source_has_stale_zones_without_confirmed_exit(self):
        self.confirm()
        self.assertFalse(self.observer.update(frame(4, 100, {}, status='unavailable')))
        self.assertFalse(self.observer.update(frame(5, 200, {}, status='unavailable')))
        stale = self.observer.snapshot()['camera:0', 0]
        self.assertEqual(stale.zone_id, 'z0')
        self.assertFalse(stale.source_available)
        self.assertFalse(stale.observed)
        self.assertEqual(stale.floor_position, POINTS[0])
        # A valid image returning after a long gap revalidates the old zone,
        # using the existing spatial engine's detection_gap behavior.
        events = self.observer.update(frame(6, 201))
        self.assertEqual(len(events), 5)
        self.assertTrue(all(e.kind == 'exit' and e.reason == 'detection_gap' for e in events))

    def test_valid_empty_frames_confirm_exit_without_using_old_position(self):
        self.confirm()
        self.assertFalse(self.observer.update(frame(4, .24, {})))
        events = self.observer.update(frame(5, .45, {}))
        self.assertEqual(len(events), 5)
        self.assertTrue(all(e.kind == 'exit' and e.reason == 'missing' for e in events))
        self.assertIsNone(self.observer.snapshot()['camera:0', 0].zone_id)

    def test_same_ids_from_two_sources_do_not_share_spatial_state(self):
        self.confirm('camera:0')
        self.confirm('camera:1')
        self.observer.update(frame(4, .24, {}, source='camera:0'))
        self.observer.update(frame(5, .45, {}, source='camera:0'))
        self.assertIsNone(self.observer.snapshot()['camera:0', 0].zone_id)
        self.assertEqual(self.observer.snapshot()['camera:1', 0].zone_id, 'z0')

    def test_invalid_frames_rejected_without_mutation_and_snapshots_immutable(self):
        self.confirm()
        before = self.observer.snapshot()
        for invalid in (frame(3, .2), frame(4, .16), object()):
            with self.assertRaises(ValueError):
                self.observer.update(invalid)
            self.assertEqual(self.observer.snapshot(), before)
        with self.assertRaises(TypeError):
            before['x'] = None
        with self.assertRaises(FrozenInstanceError):
            before['camera:0', 0].zone_id = 'changed'

    def test_map_changes_clear_runtime_unchanged_save_preserves_it_and_sources_bounded(self):
        self.confirm()
        before = self.observer.snapshot()
        self.observer.configure(config())
        self.assertEqual(self.observer.snapshot(), before)
        self.observer.configure(SpatialMap())
        self.assertFalse(self.observer.snapshot())
        limited = CommonSpatialObserver(config(), max_sources=1)
        limited.update(frame(1, 0))
        with self.assertRaises(ValueError):
            limited.update(frame(1, 0, source='camera:1'))

    def test_journal_keeps_every_zone_event_participant_and_reason_once(self):
        registry = ParticipantRegistry(ParticipantBinding(f'p{i}', str(i), '#FFFFFF', 'camera:0', i) for i in range(5))
        log = CommonEventLog(limit=2)
        last_frame = None
        for seq, now in enumerate((0, .08, .16), 1):
            last_frame = frame(seq, now)
            batch = log.record_zones(last_frame, self.observer.update(last_frame), registry)
        self.assertEqual(len(batch), 5)
        self.assertEqual([e.participant_id for e in batch], [f'p{i}' for i in range(5)])
        self.assertEqual([e.zone_id for e in batch], [f'z{i}' for i in range(5)])
        self.assertTrue(all(e.kind == 'zone_entered' and e.reason == 'movement' for e in batch))
        self.assertEqual(len(log.snapshot()), 2)
        self.assertFalse(log.record_zones(last_frame, self.confirm_events(), registry))

    def confirm_events(self):
        observer = CommonSpatialObserver(config())
        for seq, now in enumerate((0, .08, .16), 1):
            events = observer.update(frame(seq, now))
        return events

    def test_simulator_copies_map_with_synthetic_calibration_and_keeps_it_on_reset(self):
        original = config(None)
        s = SimulatorSession()
        s.configure_spatial(original)
        self.assertIsNone(original.calibration)
        self.assertIsNotNone(s.spatial.config.calibration)
        for pid, point in zip(s.registry.snapshot(), POINTS):
            s.set_pose(pid, position=point)
        for now in (0, .08, .16):
            _, events = s.advance(now)
        self.assertEqual(len([e for e in events if e.kind == 'zone_entered']), 5)
        self.assertEqual([e.zone_id for e in events], [f'z{i}' for i in range(5)])
        s.reset()
        self.assertEqual(s.spatial.config.zones, original.zones)
        self.assertFalse(s.spatial.snapshot())
        self.assertFalse(s.events.snapshot())


if __name__ == '__main__':
    unittest.main()
