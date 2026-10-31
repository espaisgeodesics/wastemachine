import json
import os
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from participant_simulator import SOURCE_ID
from participants import ParticipantBinding
from test_camera import app_module as m


@unittest.skipUnless(os.environ.get('DISPLAY') or os.name == 'nt', 'Requires a graphical display')
class SimulatorWindowTests(unittest.TestCase):
    def setUp(self):
        self.root = m.tk.Tk()
        with patch.object(m.mido, 'get_output_names', return_value=[]):
            self.app = m.App(self.root)
        self.app.arp_stop.set()
        self.app.arp_thread.join(timeout=1)
        for timer in self.root.tk.call('after', 'info'):
            self.root.after_cancel(timer)
        self.app.open_simulator()
        self.view = self.app.simulator_view
        self.session = self.app.simulator_session
        self.root.update_idletasks()

    def tearDown(self):
        if self.app.simulator_window is not None:
            self.app.simulator_window.destroy()
            self.app.simulator_window = None
            self.app.simulator_view = None
        for timer in self.root.tk.call('after', 'info'):
            self.root.after_cancel(timer)
        self.app.close()

    def select(self, pid='virtual-1'):
        self.view.editor.table.selection_set(pid)
        self.view.editor.select()

    def test_drag_moves_only_selected_person_clamps_and_does_not_start_on_empty_map(self):
        self.select()
        initial = self.session.poses()
        self.view.pick(SimpleNamespace(x=-100, y=-100))
        self.view.drag(SimpleNamespace(x=10000, y=10000))
        self.assertEqual(self.session.poses(), initial)
        x, y, width, height = self.view.bounds()
        self.view.pick(SimpleNamespace(x=x+width*.25, y=y+height*.3))
        self.view.drag(SimpleNamespace(x=10000, y=-100))
        self.assertEqual(self.session.poses()['virtual-1'].position, (1., 0.))
        self.assertEqual(self.session.poses()['virtual-2'], initial['virtual-2'])

    def test_rotation_hiding_source_failure_and_retirement_controls(self):
        self.select()
        self.view.angle.set(450)
        self.view.rotate()
        self.assertEqual(self.session.poses()['virtual-1'].orientation, .25)
        self.view.visibility(False)
        self.session.advance(time.monotonic())
        self.assertEqual(self.session.registry.states(self.session.tracker.snapshot())['virtual-1'].presence, 'temporarily_lost')
        self.view.visibility(True)
        self.view.editor.set_retired(True)
        self.session.advance(time.monotonic())
        self.assertEqual(self.session.registry.states(self.session.tracker.snapshot())['virtual-1'].presence, 'retired')
        self.view.editor.set_retired(False)
        self.view.available.set(False)
        self.view.change_source()
        self.session.advance(time.monotonic())
        self.view.editor.refresh_rows()
        self.assertIn('NO DISPONIBLE', self.view.editor.source_status.get())
        self.assertEqual(len(self.session.registry.snapshot()), 5)
        self.view.available.set(True)
        self.view.change_source()
        self.session.advance(time.monotonic())
        self.assertTrue(all(s.observed for s in self.session.registry.states(self.session.tracker.snapshot()).values()))

    def test_simulator_keeps_camera_project_participants_midi_and_public_frames_unchanged(self):
        self.app.midi = Mock()
        self.app.participants.upsert(ParticipantBinding('real', 'Persona real', '#FFFFFF', 'camera:0', 0))
        config = self.app.participants.to_dict()
        cards = json.loads(json.dumps(self.app.cards))
        tracker = self.app.marker_tracker.snapshot()
        events = self.app.common_events.snapshot()
        before = self.app.compose_output_frame(1).copy()
        self.select()
        self.view.angle.set(180)
        self.view.rotate()
        self.view.visibility(False)
        self.view.retire('virtual-2', True)
        self.session.advance(time.monotonic())
        self.assertEqual(self.app.participants.to_dict(), config)
        self.assertEqual(self.app.cards, cards)
        self.assertEqual(self.app.marker_tracker.snapshot(), tracker)
        self.assertEqual(self.app.common_events.snapshot(), events)
        self.assertIsNone(self.app.camera)
        self.app.midi.send.assert_not_called()
        m.np.testing.assert_array_equal(self.app.compose_output_frame(1), before)

    def test_editor_renames_and_reassigns_virtual_people_without_real_source_bindings(self):
        self.select()
        self.view.editor.name.set('Mar')
        self.view.editor.marker.set('15')
        self.view.editor.color.set('#FFCC00')
        self.assertTrue(self.view.editor.apply())
        self.assertIn('sessió de proves', self.view.editor.notice.get())
        self.assertNotIn('Desa el projecte', self.view.editor.notice.get())
        p = self.session.registry.snapshot()['virtual-1']
        self.assertEqual((p.name, p.marker_id, p.color), ('Mar', 15, '#FFCC00'))
        self.view.editor.source.set('camera:0')
        with patch('participant_editor.messagebox.showerror') as error:
            self.assertFalse(self.view.editor.apply())
        error.assert_called_once()
        self.assertEqual(self.session.registry.snapshot()['virtual-1'].source_id, SOURCE_ID)

    def test_closing_and_reopening_retains_session_and_cancels_both_timers(self):
        self.session.set_pose('virtual-1', position=(.7, .8))
        timers = (self.view.timer, self.view.editor._timer)
        window = self.app.simulator_window
        self.app.open_simulator()
        self.assertIs(self.app.simulator_window, window)
        window.tk.call(window.protocol('WM_DELETE_WINDOW'))
        for timer in timers:
            self.assertNotIn(timer, self.root.tk.call('after', 'info'))
        self.assertIsNone(self.app.simulator_view)
        self.app.open_simulator()
        self.view = self.app.simulator_view
        self.assertIs(self.app.simulator_session, self.session)
        self.assertEqual(self.session.poses()['virtual-1'].position, (.7, .8))

    def test_pending_virtual_form_can_cancel_window_close(self):
        self.select()
        self.view.editor.name.set('Pendent')
        window = self.app.simulator_window
        with patch('participant_editor.messagebox.askyesno', return_value=False):
            window.tk.call(window.protocol('WM_DELETE_WINDOW'))
        self.assertTrue(window.winfo_exists())
        self.assertTrue(self.view.editor.dirty)

    def test_reset_requires_confirmation_and_keeps_real_registry_untouched(self):
        self.session.set_pose('virtual-1', position=(.8, .9))
        self.app.participants.upsert(ParticipantBinding('real', 'Real', '#FFFFFF', 'camera:0', 0))
        before = self.app.participants.to_dict()
        with patch('simulator_window.messagebox.askyesno', return_value=False):
            self.view.reset()
        self.assertEqual(self.session.poses()['virtual-1'].position, (.8, .9))
        with patch('simulator_window.messagebox.askyesno', return_value=True):
            self.view.reset()
        self.assertEqual(self.session.poses()['virtual-1'].position, (.25, .3))
        self.assertFalse(self.session.events.snapshot())
        self.assertEqual(self.app.participants.to_dict(), before)

    def test_loading_project_zones_isolated_and_events_and_current_zone_are_visible(self):
        from spatial_zones import SpatialMap, Zone
        self.app.spatial_map=SpatialMap(zones=(Zone('forest','Bosc',{(2,2)},{0},'not-loaded.png'),))
        original=self.app.spatial_map
        self.view.load_zones()
        self.assertIs(self.app.spatial_map,original)
        self.assertIsNone(original.calibration)
        self.assertIsNotNone(self.session.spatial.config.calibration)
        self.session.set_pose('virtual-1',position=(.3,.3))
        now=time.monotonic()
        for offset in (.01,.09,.17):self.session.advance(now+offset)
        self.view.editor.refresh_rows()
        self.assertEqual(self.view.editor.table.item('virtual-1','values')[6],'Bosc')
        events=[e for e in self.session.events.snapshot() if e.kind=='zone_entered']
        self.assertEqual([(e.participant_id,e.zone_id) for e in events],[('virtual-1','forest')])
        self.assertEqual(events[0].zone_name,'Bosc')
        self.assertIsNone(self.app.zone_projection.image)
        self.assertFalse(self.app.common_spatial.snapshot())
        self.session.available=False
        self.session.advance(now+1)
        self.view.editor.refresh_rows()
        self.assertEqual(self.view.editor.table.item('virtual-1','values')[6],'Bosc (antiga)')


if __name__ == '__main__':
    unittest.main()
