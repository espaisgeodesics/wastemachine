import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from spatial_zones import (Calibration, Grid, SpatialEngine, SpatialMap,
                           Stabilization, Zone, check_image_asset, image_reference)


def zone(id='forest', cells=((3, 2), (4, 2)), cards=(4,), image='images/bosc.jpg', enabled=True):
    return Zone(id, id, frozenset(cells), frozenset(cards), image, enabled)


def engine(zones=None, **options):
    return SpatialEngine(SpatialMap(zones=tuple(zones or [zone()]), stabilization=Stabilization(**options)))


def confirm(e, card=4, point=(.3, .45), start=0):
    results = [e.update_normalized({card: point}, start + offset) for offset in (0, .08, .16)]
    return results[-1]


class GridAndValidationTests(unittest.TestCase):
    def test_circle_and_grid_edges(self):
        grid = Grid()
        self.assertIsNone(grid.cell_at((0, 0)))
        self.assertIsNone(grid.cell_at((1.001, .5)))
        self.assertEqual(grid.cell_at((.5, 0)), (0, 4))
        self.assertEqual(grid.cell_at((1, .5)), (4, 7))
        self.assertEqual(grid.cell_at((.5, 1)), (7, 4))
        self.assertFalse(grid.eligible((0, 0)))
        self.assertTrue(grid.eligible((0, 2)))  # Partial intersection, not just cell center.
        self.assertEqual(sum(grid.eligible((r, c)) for r in range(8) for c in range(8)), 60)

    def test_active_overlap_rejected_but_disabled_draft_is_allowed(self):
        with self.assertRaisesRegex(ValueError, 'overlap'):
            SpatialMap(zones=(zone(), zone('desert', image='desert.png')))
        config = SpatialMap(zones=(zone(), zone('draft', enabled=False)))
        self.assertEqual(confirm(SpatialEngine(config)).scene.zone_id, 'forest')

    def test_invalid_zone_definitions(self):
        cases = [lambda: SpatialMap(zones=(zone(cells=((0, 0),)),)),
                 lambda: SpatialMap(zones=(zone(cells=((8, 2),)),)),
                 lambda: SpatialMap(zones=(zone(), zone(image='other.png'))),
                 lambda: zone(cards=(16,)), lambda: zone(cards=(True,)),
                 lambda: zone(cells=()), lambda: zone(image='clip.mp4'),
                 lambda: Zone('', 'name', {(3, 3)}, {1}),
                 lambda: SpatialMap(stabilization=Stabilization(hysteresis=.08))]
        for create in cases:
            with self.subTest(create=create), self.assertRaises(ValueError):
                create()

    def test_no_authorized_cards_means_no_activation(self):
        self.assertIsNone(confirm(engine([zone(cards=())])).scene)


class CalibrationTests(unittest.TestCase):
    def test_perspective_maps_reference_and_interior_points(self):
        # Known projective distortion of the unit floor into a camera image.
        def distort(point):
            x, y = point
            d = 1 + .2*x + .1*y
            return ((.7*x + .05*y + .1)/d, (.02*x + .75*y + .1)/d)
        floor = ((.5, 0), (1, .5), (.5, 1), (0, .5))
        calibration = Calibration(tuple(distort(p) for p in floor))
        for point in (*floor, (.3, .45), (.55, .65)):
            with self.subTest(point=point):
                result = calibration.project(distort(point))
                self.assertAlmostEqual(result[0], point[0], places=8)
                self.assertAlmostEqual(result[1], point[1], places=8)
        config = SpatialMap(zones=(zone(),), calibration=calibration)
        e = SpatialEngine(config)
        for now in (0, .08, .16):result = e.update_camera({4: distort((.3, .45))}, now)
        self.assertEqual(result.scene.zone_id, 'forest')

    def test_invalid_quads_rejected(self):
        for points in [((.1, .1),)*4,
                       ((0, 0), (.2, .2), (.4, .4), (.6, .6)),
                       ((0, 0), (1, 1), (1, 0), (0, 1)),
                       ((-.1, 0), (1, 0), (1, 1), (0, 1))]:
            with self.subTest(points=points), self.assertRaises(ValueError):
                Calibration(points)

    def test_horizon_outside_reference_quad_but_inside_floor_is_rejected(self):
        floor = ((.5, 0), (1, .5), (.5, 1), (0, .5))
        def distorted(p):
            x,y=p;denominator=x+y-.4
            return (.5+.01*(x-.5)/denominator,.5+.01*(y-.5)/denominator)
        with self.assertRaisesRegex(ValueError,'horizon'):
            Calibration(tuple(distorted(p) for p in floor))

    def test_calibrated_circle_boundary_has_no_roundoff_exclusion(self):
        calibration=Calibration(((.5,.1),(.9,.5),(.5,.9),(.1,.5)))
        grid=Grid()
        for camera,expected in zip(calibration.camera_points,((0,4),(4,7),(7,4),(4,0))):
            self.assertEqual(grid.cell_at(calibration.project(camera)),expected)

    def test_camera_input_without_calibration_never_uses_identity(self):
        e = engine()
        for now in (0, .08, .16):result = e.update_camera({4: (.3, .45)}, now)
        self.assertEqual(result.status, 'uncalibrated')
        self.assertFalse(result.events)
        self.assertIsNone(result.scene)


class DetectionTests(unittest.TestCase):
    def test_enter_exit_latch_second_zone_and_stationary_no_reload(self):
        e = engine([zone(), zone('desert', ((3, 5),), image='desert.png')])
        first = confirm(e)
        self.assertTrue(first.scene_changed);self.assertTrue(first.image_changed)
        self.assertEqual(first.scene.zone_id, 'forest')
        stable_scene = e.scene
        for now in (.20, .24, .28):
            stationary = e.update_normalized({4: (.3, .45)}, now)
            self.assertFalse(stationary.events)
            self.assertFalse(stationary.image_changed)
        e.update_normalized({4: (.5, .8)}, .36)
        e.update_normalized({4: (.5, .8)}, .46)
        exited = e.update_normalized({4: (.5, .8)}, .57)
        self.assertEqual([(x.kind, x.zone_id) for x in exited.events], [('exit', 'forest')])
        self.assertIs(e.scene, stable_scene)
        second = confirm(e, point=(.7, .45), start=.65)
        self.assertEqual(second.scene.zone_id, 'desert');self.assertTrue(second.image_changed)
        e.update_normalized({}, .9)
        lost = e.update_normalized({}, 1.11)
        self.assertEqual(lost.events[0].reason, 'missing')
        self.assertEqual(e.scene.zone_id, 'desert')
        self.assertIsNone(e.confirmed_zone(4))
        self.assertEqual(e.last_entered_zone(4), 'desert')

    def test_unauthorized_card_cannot_change_scene(self):
        e = engine();confirm(e)
        for now in (.24, .32, .40):result = e.update_normalized({7: (.3, .45)}, now)
        self.assertFalse(any(x.kind == 'enter' for x in result.events))
        self.assertEqual(e.scene.card_id, 4)

    def test_grouped_cells_have_one_entry(self):
        e = engine();confirm(e)
        events = []
        for now in (.24, .32, .40):events.extend(e.update_normalized({4: (.3, .55)}, now).events)
        self.assertFalse(events)
        self.assertEqual(e.confirmed_zone(4), 'forest')

    def test_hysteresis_holds_boundary_then_confirms_new_zone(self):
        e = engine([zone(cells=((3, 3),)), zone('right', ((3, 4),), image='right.png')])
        confirm(e, point=(.49, .45))
        for now, x in ((.24, .502), (.32, .498), (.40, .505)):
            self.assertFalse(e.update_normalized({4: (x, .45)}, now).events)
            self.assertEqual(e.confirmed_zone(4), 'forest')
        result = confirm(e, point=(.53, .45), start=.48)
        self.assertEqual([(x.kind, x.zone_id) for x in result.events], [('exit', 'forest'), ('enter', 'right')])

    def test_time_and_consecutive_detection_requirements_are_both_enforced(self):
        e = engine()
        for now in (0, .01, .02, .03):self.assertIsNone(e.update_normalized({4: (.3, .45)}, now).scene)
        self.assertIsNotNone(e.update_normalized({4: (.3, .45)}, .16).scene)
        e = engine()
        e.update_normalized({4: (.3, .45)}, 0)
        e.update_normalized({}, .08)
        self.assertIsNone(e.update_normalized({4: (.3, .45)}, .16).scene)
        self.assertIsNone(e.update_normalized({4: (.3, .45)}, .24).scene)
        self.assertIsNotNone(e.update_normalized({4: (.3, .45)}, .32).scene)

    def test_long_detection_gap_requires_new_stabilization(self):
        e = engine();confirm(e)
        result = e.update_normalized({4: (.3, .45)}, 2)
        self.assertEqual(result.events[0].reason, 'detection_gap')
        self.assertIsNone(e.confirmed_zone(4));self.assertEqual(e.scene.zone_id, 'forest')
        e.update_normalized({4: (.3, .45)}, 2.08)
        result = e.update_normalized({4: (.3, .45)}, 2.16)
        self.assertEqual(result.events[-1].kind, 'enter')
        self.assertFalse(result.image_changed)

    def test_reentry_records_event_without_reloading_same_scene(self):
        e = engine();confirm(e)
        e.update_normalized({}, .24);e.update_normalized({}, .45)
        result = confirm(e, start=.53)
        self.assertEqual(result.events[0].kind, 'enter')
        self.assertFalse(result.scene_changed);self.assertFalse(result.image_changed)

    def test_different_zones_sharing_image_do_not_request_reload(self):
        e = engine([zone(), zone('second', ((3, 5),))]);confirm(e)
        result = confirm(e, point=(.7, .45), start=.24)
        self.assertTrue(result.scene_changed);self.assertFalse(result.image_changed)
        self.assertEqual(result.scene.zone_id, 'second')

    def test_simultaneous_entries_have_deterministic_priority(self):
        configs = [zone(cards=(4,)), zone('second', ((3, 5),), cards=(2,), image='second.png')]
        winners = []
        for observations in ({4: (.3, .45), 2: (.7, .45)}, {2: (.7, .45), 4: (.3, .45)}):
            e = engine(configs)
            for now in (0, .08, .16):result = e.update_normalized(observations, now)
            winners.append(result.scene.zone_id)
            self.assertEqual(len([x for x in result.events if x.kind == 'enter']), 2)
        self.assertEqual(winners, ['second', 'second'])

    def test_zone_without_image_does_not_replace_scene(self):
        e = engine([zone(), zone('empty', ((3, 5),), image=None)]);confirm(e)
        result = confirm(e, point=(.7, .45), start=.24)
        self.assertEqual(e.confirmed_zone(4), 'empty')
        self.assertEqual(result.scene.zone_id, 'forest');self.assertFalse(result.scene_changed)

    def test_invalid_frame_does_not_partially_change_state(self):
        e = engine()
        e.update_normalized({4: (.3, .45)}, 0)
        for observations, now in [({4: (.3, .45)}, 0), ({16: (.3, .45)}, .08),
                                  ({4: (float('nan'), .45)}, .08), ({True: (.3, .45)}, .08)]:
            with self.subTest(observations=observations), self.assertRaises(ValueError):
                e.update_normalized(observations, now)
        self.assertIsNone(e.update_normalized({4: (.3, .45)}, .08).scene)
        self.assertIsNotNone(e.update_normalized({4: (.3, .45)}, .16).scene)


class PersistenceAndAssetTests(unittest.TestCase):
    def test_json_roundtrip_and_legacy_project(self):
        calibration = Calibration(((.5, .1), (.9, .5), (.5, .9), (.1, .5)))
        config = SpatialMap(zones=(zone(),), calibration=calibration)
        project = {'version': 4, 'cards': [{'function': 'Nota MIDI', 'note': 60}], 'bpm': 120}
        combined = config.into_project(project)
        self.assertNotIn('spatial_zones', project)
        self.assertEqual(combined['cards'], project['cards'])
        decoded = SpatialMap.from_project(json.loads(json.dumps(combined)))
        self.assertEqual(config.to_dict(), decoded.to_dict())
        self.assertEqual(SpatialMap.from_project(project), SpatialMap())
        self.assertEqual(SpatialMap.from_project({'spatial_zones': None}), SpatialMap())
        with self.assertRaises(ValueError):SpatialMap.from_dict({'schema_version': 99})

    def test_invalid_saved_configuration_does_not_silently_enable_map(self):
        data = SpatialMap(zones=(zone(),)).to_dict()
        data['zones'].append(dict(data['zones'][0], id='duplicate_cells'))
        with self.assertRaisesRegex(ValueError, 'overlap'):SpatialMap.from_dict(data)
        data['zones'] = []
        data['calibration'] = {'camera_points': [[0, 0]] * 4}
        with self.assertRaises(ValueError):SpatialMap.from_dict(data)

    def test_missing_files_and_relative_paths_are_reported_without_loading(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder);project = root / 'project.json'
            image = root / 'imatges' / 'bosc bonic.png';image.parent.mkdir();image.write_bytes(b'not decoded in phase 1')
            reference = image_reference(image, project)
            self.assertEqual(reference, 'imatges/bosc bonic.png')
            self.assertEqual(check_image_asset(reference, project).status, 'exists')
            self.assertEqual(check_image_asset('missing.jpg', project).status, 'missing')
            self.assertEqual(check_image_asset(reference, None).status, 'unresolved')
            self.assertEqual(check_image_asset(None, project).status, 'not_assigned')
            self.assertEqual(check_image_asset('video.mp4', project).status, 'unsupported')
            outside = root.parent / 'external.png'
            self.assertTrue(Path(image_reference(outside, project)).is_absolute())
            with patch.object(Path, 'is_file', side_effect=PermissionError('denied')):
                self.assertEqual(check_image_asset(reference, project).status, 'unreadable')
            # A missing asset is only a scene request; the engine does no I/O.
            result = confirm(engine([zone(image='missing.jpg')]))
            self.assertEqual(result.scene.image_path, 'missing.jpg')


if __name__ == '__main__':
    unittest.main()
