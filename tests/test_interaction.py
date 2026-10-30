import os
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from test_camera import app_module as m

def close_test_app(app):
    # Each test owns its Tcl interpreter; cancel callbacks before destroying it.
    for timer in app.root.tk.call('after','info'):app.root.after_cancel(timer)
    app.close()

@unittest.skipUnless(os.environ.get('DISPLAY') or os.name=='nt','Requires a graphical display')
class InteractionTests(unittest.TestCase):
    def test_mouse_music_settings_and_project_roundtrip(self):
        root=m.tk.Tk()
        try:
            with patch.object(m.mido,'get_output_names',return_value=[]):a=m.App(root)
            a.arp_stop.set();a.arp_thread.join(timeout=1)
            root.update()
            a.midi=Mock();a.simulation.set(True);a.toggle_simulation()
            a.vis_label.update_idletasks()
            event=SimpleNamespace(x=a.vis_label.winfo_width()/2,y=a.vis_label.winfo_height()/2)
            a.simulation_press(event)
            self.assertIn(0,a.active)
            self.assertAlmostEqual(a.active[0][0],.5,places=2)
            self.assertEqual(a.midi.send.call_args.args[0].type,'note_on')
            a.simulation_release()
            self.assertNotIn(0,a.active)
            self.assertEqual(a.midi.send.call_args.args[0].type,'note_off')
            for kind in ('Arpegiador espacial','Patró rítmic','Ritme de bateria'):
                a.fun.set(kind);a.on_function_selected()
                self.assertTrue(a.music_settings_window.winfo_exists())
                a.music_settings_window.destroy()
            a.fun.set('Patró rítmic');a.arp_direction.set('Descendent');a.channel.set(10);a.note.set(36)
            for j,var in enumerate(a.rhythm_steps):var.set(j in (0,4,8,12))
            a.apply_card()
            a.simulation_press(event)
            self.assertIn(0,a.arp_states)
            a.toggle_panic()
            self.assertTrue(a.muted);self.assertFalse(a.arp_states);self.assertFalse(a.active)
            a.simulation_press(event);self.assertFalse(a.active)
            a.toggle_panic()
            a.fun.set('Ritme de bateria');a.drum_preset.set('Disco');a.drum_notes['Caixa'].set(40)
            a.apply_card();a.simulation_press(event)
            a.sequencer_tick(a.metronome_start)
            hits=[c.args[0].note for c in a.midi.send.call_args_list if c.args[0].type=='note_on']
            self.assertIn(36,hits);self.assertIn(42,hits)
            a.simulation_release()
            with tempfile.TemporaryDirectory() as folder:
                a.project=str(Path(folder)/'project.json');a.save_project()
                a.cards[0]['function']='Cap acció'
                with patch.object(m.filedialog,'askopenfilename',return_value=a.project):a.open_project()
                self.assertEqual(a.cards[0]['function'],'Ritme de bateria')
                self.assertEqual(a.drum_preset.get(),'Disco')
                self.assertEqual(a.drum_notes['Caixa'].get(),40)
                self.assertEqual(a.cards[0]['arp_direction'],'Descendent')
                self.assertEqual([v.get() for v in a.rhythm_steps],[j in (0,4,8,12) for j in range(16)])
            close_test_app(a)
        finally:
            try:root.destroy()
            except m.tk.TclError:pass

    def test_assigned_card_selection_previews_without_midi_or_recording_changes(self):
        import numpy as np
        root=m.tk.Tk()
        try:
            with patch.object(m.mido,'get_output_names',return_value=[]):a=m.App(root)
            a.arp_stop.set();a.arp_thread.join(timeout=1)
            root.update()
            a.midi=Mock()
            a.cards[15]['function']='Cap acció'
            a.cards[2]['function']='Arpegiador espacial'
            a.cards[2]['harmony_scale']='Dòrica'
            a.update_assigned_cards()
            self.assertFalse(a.assigned_cards.exists('15'))
            a.assigned_cards.selection_set('2')
            a.assigned_cards.event_generate('<<TreeviewSelect>>')
            root.update()
            self.assertEqual(a.preview_card,2)
            self.assertEqual(a.card_id.get(),'03')
            self.assertEqual(a.fun.get(),'Arpegiador espacial')
            self.assertEqual(a.harmony_scale.get(),'Dòrica')
            self.assertFalse(a.active)
            self.assertFalse(a.arp_states)
            a.midi.send.assert_not_called()
            visual=a.current_visual
            live_frame=np.full((360,640,3),17,np.uint8)
            a.last_frame=live_frame.copy();a.visual_paused=True
            a.recording=Mock();a.preview_dirty=True
            a.tick()
            np.testing.assert_array_equal(a.recording.write.call_args.args[0],live_frame)
            self.assertEqual(a.current_visual,visual)
            self.assertTrue(hasattr(a,'vis_photo'))
            for kind in m.FUNCS:
                if kind=='Cap acció':continue
                a.cards[2]['function']=kind
                frame=a.card_preview_frame(2,1.0)
                self.assertEqual(frame.shape,(360,640,3))
                self.assertEqual(frame.dtype,np.uint8)
                self.assertGreater(frame.std(),0)
            a.midi.send.assert_not_called()
            a.follow_live_preview();root.update()
            self.assertIsNone(a.preview_card)
            self.assertFalse(a.assigned_cards.selection())
            a.cards[2]['function']='Cap acció';a.update_assigned_cards()
            self.assertFalse(a.assigned_cards.exists('2'))
            close_test_app(a)
        finally:
            try:root.destroy()
            except m.tk.TclError:pass

    def test_independent_card_window_names_and_layout_persist(self):
        root=m.tk.Tk()
        try:
            with patch.object(m.mido,'get_output_names',return_value=[]):a=m.App(root)
            a.arp_stop.set();a.arp_thread.join(timeout=1);root.update()
            a.midi=Mock()
            self.assertIs(a.assigned_cards.winfo_toplevel(),a.cards_window)
            self.assertIsNot(a.cards_window,a.visual_window)
            self.assertEqual(tuple(a.assigned_cards['columns']),('card','function','name'))
            a.show_panel('cards');a.assigned_cards.selection_set('0');root.update()
            with patch.object(m.simpledialog,'askstring',return_value='Bateria principal – Jordi'):
                a.edit_card_name()
            self.assertEqual(a.cards[0]['name'],'Bateria principal – Jordi')
            self.assertEqual(a.assigned_cards.item('0','values')[2],'Bateria principal – Jordi')
            with patch.object(m.simpledialog,'askstring',return_value=None):a.edit_card_name()
            self.assertEqual(a.cards[0]['name'],'Bateria principal – Jordi')
            with tempfile.TemporaryDirectory() as folder:
                a.project=str(Path(folder)/'project.json');a.save_project()
                a.cards[0]['name']='Canvi temporal'
                with patch.object(m.filedialog,'askopenfilename',return_value=a.project):a.open_project()
                self.assertEqual(a.cards[0]['name'],'Bateria principal – Jordi')
                self.assertEqual(a.assigned_cards.item('0','values')[2],'Bateria principal – Jordi')
                a.window_layout_file=Path(folder)/'layout.json'
                a.cards_window.geometry('600x400+60+70');root.update_idletasks()
                a.save_window_layout();a.cards_window.withdraw();a.restore_window_layout()
                root.update_idletasks()
                self.assertEqual(a.cards_window.state(),'normal')
                self.assertEqual(a.cards_window.geometry(),'600x400+60+70')
            a.midi.send.assert_not_called()
            close_test_app(a)
        finally:
            try:root.destroy()
            except m.tk.TclError:pass

if __name__=='__main__':unittest.main()
