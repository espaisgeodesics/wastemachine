import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from marker_tracking import MarkerObservation, ObservationFrame
from participants import ParticipantBinding
from test_camera import app_module as m


@unittest.skipUnless(os.environ.get('DISPLAY') or os.name == 'nt', 'Requires a graphical display')
class ParticipantEditorTests(unittest.TestCase):
    def setUp(self):
        self.root = m.tk.Tk()
        with patch.object(m.mido, 'get_output_names', return_value=[]):
            self.app = m.App(self.root)
        self.app.arp_stop.set()
        self.app.arp_thread.join(timeout=1)
        self.app.open_participants()
        self.editor = self.app.participant_editor
        self.folder = TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)

    def tearDown(self):
        if self.app.participant_window is not None:
            self.app.participant_window.destroy()
            self.app.participant_window = None
            self.app.participant_editor = None
        for timer in self.root.tk.call('after', 'info'):
            self.root.after_cancel(timer)
        self.app.close()

    def add_person(self, name='Laia', marker='0', color='#00CC88'):
        self.editor.name.set(name)
        self.editor.color.set(color)
        self.editor.marker.set(marker)
        self.assertTrue(self.editor.apply())
        return self.editor.selected_id

    def test_edit_assign_choose_color_and_reopen_window(self):
        self.app.midi = Mock()
        cards = json.loads(json.dumps(self.app.cards))
        pid = self.add_person()
        self.editor.name.set('Laia editada')
        self.editor.marker.set('4')
        with patch('participant_editor.colorchooser.askcolor', return_value=((255, 0, 0), '#ff0000')):
            self.editor.choose_color()
        self.assertTrue(self.editor.apply())
        person = self.app.participants.snapshot()[pid]
        self.assertEqual((person.name, person.marker_id, person.color), ('Laia editada', 4, '#FF0000'))
        self.assertEqual(self.app.cards, cards)
        self.app.midi.send.assert_not_called()
        window = self.app.participant_window
        self.app.open_participants()
        self.assertIs(self.app.participant_window, window)

    def test_duplicate_assignment_does_not_change_registry_or_discard_form(self):
        self.add_person()
        self.editor.new()
        self.editor.name.set('Pau')
        self.editor.marker.set('0')
        with patch('participant_editor.messagebox.showerror') as error:
            self.assertFalse(self.editor.apply())
        error.assert_called_once()
        self.assertEqual(len(self.app.participants.snapshot()), 1)
        self.assertTrue(self.editor.dirty)

    def test_retirement_preserves_physical_tracking_and_has_no_outputs(self):
        pid = self.add_person()
        self.app.update_common_tracking(ObservationFrame('camera:0', 1, 1, (MarkerObservation(0, (.2, .3), 0),)))
        before = self.app.compose_output_frame(1).copy()
        self.app.midi = Mock()
        self.editor.set_retired(True)
        self.editor.refresh_rows()
        self.assertEqual(self.editor.table.item(pid, 'values')[4], 'Retirat de la sessió')
        self.assertTrue(self.app.marker_tracker.snapshot()['camera:0', 0].observed)
        self.assertEqual(self.app.common_events.snapshot()[-1].kind, 'participant_retired')
        m.np.testing.assert_array_equal(self.app.compose_output_frame(1), before)
        self.app.midi.send.assert_not_called()
        self.editor.set_retired(False)
        self.assertEqual(self.app.participants.states(self.app.marker_tracker.snapshot())[pid].presence, 'detected')

    def test_stale_position_and_source_unavailable_are_visible(self):
        pid = self.add_person()
        self.app.update_common_tracking(ObservationFrame('camera:0', 1, 1, (MarkerObservation(0, (.2, .3), 0),)))
        self.app.update_common_tracking(ObservationFrame('camera:0', 2, 100, status='unavailable'))
        self.editor.refresh_rows()
        values = self.editor.table.item(pid, 'values')
        self.assertEqual(values[4], 'Perdut temporalment')
        self.assertIn('(antiga)', values[5])
        self.assertIn('NO DISPONIBLE', self.editor.source_status.get())
        self.assertEqual(len(self.editor.event_table.get_children()), 4)

    def save(self, path):
        with patch.object(m.filedialog, 'asksaveasfilename', return_value=str(path)):
            self.app.save_project(True)
        self.assertTrue(path.exists())
        return json.loads(path.read_text(encoding='utf-8'))

    def open(self, path):
        with patch.object(m.filedialog, 'askopenfilename', return_value=str(path)):
            self.app.open_project()

    def test_project_save_as_roundtrip_and_legacy_load_preserve_cards_and_spatial(self):
        pid = self.add_person()
        self.editor.set_retired(True)
        path = Path(self.folder.name) / 'session.json'
        data = self.save(path)
        expected = self.app.participants.to_dict()
        self.assertEqual(data['version'], 4)
        self.assertEqual(data['participants'], expected)
        self.assertEqual(data['cards'], self.app.cards)
        self.app.new_project()
        self.assertFalse(self.app.participants.snapshot())
        self.open(path)
        self.assertEqual(self.app.participants.to_dict(), expected)
        self.assertEqual(self.app.participants.states({})[pid].presence, 'not_seen')
        self.assertEqual(self.app.cards, data['cards'])
        copy = Path(self.folder.name) / 'copy.json'
        self.assertEqual(self.save(copy)['participants'], expected)
        data.pop('participants')
        legacy = Path(self.folder.name) / 'legacy.json'
        legacy.write_text(json.dumps(data), encoding='utf-8')
        self.open(legacy)
        self.assertFalse(self.app.participants.snapshot())
        self.assertEqual(self.app.cards, data['cards'])

    def test_invalid_participant_project_does_not_mutate_existing_project_or_send_midi(self):
        self.add_person()
        path = Path(self.folder.name) / 'good.json'
        data = self.save(path)
        before = self.app.participants.to_dict()
        before_cards = json.loads(json.dumps(self.app.cards))
        data['participants']['bindings'].append(dict(data['participants']['bindings'][0], participant_id='duplicate'))
        bad = Path(self.folder.name) / 'bad.json'
        bad.write_text(json.dumps(data), encoding='utf-8')
        self.app.midi = Mock()
        with patch.object(m.messagebox, 'showerror') as error:
            self.open(bad)
        error.assert_called_once()
        self.assertEqual(self.app.participants.to_dict(), before)
        self.assertEqual(self.app.cards, before_cards)
        self.assertEqual(self.app.project, str(path))
        self.app.midi.send.assert_not_called()

    def test_pending_form_blocks_save_and_declining_discard_preserves_new_project(self):
        pid = self.add_person()
        self.editor.name.set('Sense aplicar')
        path = Path(self.folder.name) / 'should-not-exist.json'
        with patch.object(m.filedialog, 'asksaveasfilename', return_value=str(path)), patch.object(m.messagebox, 'showwarning') as warning:
            self.app.save_project(True)
        warning.assert_called_once()
        self.assertFalse(path.exists())
        with patch('participant_editor.messagebox.askyesno', return_value=False):
            self.app.new_project()
        self.assertIn(pid, self.app.participants.snapshot())
        self.assertEqual(self.editor.name.get(), 'Sense aplicar')

    def test_close_and_reopen_cancels_editor_timer_and_keeps_registration(self):
        pid = self.add_person()
        timer = self.editor._timer
        window = self.app.participant_window
        window.tk.call(window.protocol('WM_DELETE_WINDOW'))
        self.assertIsNone(self.app.participant_editor)
        self.assertNotIn(timer, self.root.tk.call('after', 'info'))
        self.app.open_participants()
        self.editor = self.app.participant_editor
        self.assertIn(pid, self.editor.table.get_children())


if __name__ == '__main__':
    unittest.main()
