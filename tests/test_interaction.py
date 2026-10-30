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
            a.sequencer_tick(a.clock_start)
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
            a.last_frame=live_frame.copy();a.visual_paused=True;a.visual_dirty=False
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
            self.assertEqual(tuple(a.assigned_cards['columns'])[:3],('card','function','name'))
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
                a.cards_window.geometry('800x400+60+70');root.update_idletasks()
                a.save_window_layout();a.cards_window.withdraw();a.restore_window_layout()
                root.update_idletasks()
                self.assertEqual(a.cards_window.state(),'normal')
                self.assertEqual(a.cards_window.geometry(),'800x400+60+70')
            a.midi.send.assert_not_called()
            close_test_app(a)
        finally:
            try:root.destroy()
            except m.tk.TclError:pass

    def test_unified_live_monitor_cc_dialog_and_projection(self):
        import numpy as np
        root=m.tk.Tk()
        try:
            with patch.object(m.mido,'get_output_names',return_value=[]):a=m.App(root)
            a.arp_stop.set();a.arp_thread.join(timeout=1);root.update()
            a.midi=Mock();a.open_aruco_monitor()
            self.assertEqual(a.cards_window.state(),'normal')
            self.assertIsNone(a.monitor_window)
            self.assertIn('angle',a.assigned_cards['columns'])
            a.cards[15]['function']='Cap acció';a.show_only_assigned.set(False);a.update_assigned_cards()
            self.assertTrue(a.assigned_cards.exists('15'))
            a.card_id.set('04');a.load_card();a.fun.set('Control MIDI CC');a.on_function_selected()
            self.assertTrue(a.cc_settings_window.winfo_exists())
            a.axis.set('Vertical');a.cc.set(11);a.apply_card();a.cc_settings_window.destroy()
            self.assertEqual(a.cards[3]['axis'],'Vertical')
            a.activate(3,.2,.75,0)
            self.assertEqual(a.midi.send.call_args.args[0].control,11)
            self.assertEqual(a.midi.send.call_args.args[0].value,95)
            a.update_assigned_cards()
            self.assertEqual(a.assigned_cards.item('3','values')[4],'ACTIU')
            self.assertEqual(a.assigned_cards.item('3','values')[10],'20.0')
            a.open_projection();root.update_idletasks()
            a.display=Mock();a.visual_dirty=True;a.tick()
            projected=[c.args[1] for c in a.display.call_args_list if c.args[0] is a.proj_label][-1]
            previewed=[c.args[1] for c in a.display.call_args_list if c.args[0] is a.vis_label][-1]
            np.testing.assert_array_equal(projected,m.cv2.cvtColor(a.last_frame,m.cv2.COLOR_BGR2RGB))
            self.assertFalse(np.array_equal(projected,previewed))
            self.assertTrue(projected.any())
            a.deactivate(3);a.tick()
            self.assertFalse(a.last_frame.any())
            projected=[c.args[1] for c in a.display.call_args_list if c.args[0] is a.proj_label][-1]
            self.assertFalse(projected.any())
            close_test_app(a)
        finally:
            try:root.destroy()
            except m.tk.TclError:pass

    def test_clean_controls_audio_dialog_and_project_persistence(self):
        root=m.tk.Tk()
        try:
            with patch.object(m.mido,'get_output_names',return_value=[]):a=m.App(root)
            a.arp_stop.set();a.arp_thread.join(timeout=1);root.update()
            def texts(widget):
                result=[]
                try:result.append(str(widget.cget('text')))
                except m.tk.TclError:pass
                for child in widget.winfo_children():result.extend(texts(child))
                return result
            labels=texts(root)
            self.assertEqual(labels.count('v'+m.APP_VERSION),0)
            self.assertNotIn('TARGETES  ·  MÚSICA  ·  VISUALS',labels)
            self.assertNotIn('FINESTRES',labels)
            self.assertNotIn('METRÒNOM: OFF',labels)
            self.assertFalse(hasattr(a,'function_settings_button'))
            self.assertIsNotNone(a.banner_source)
            a.midi=Mock();a.card_id.set('05');a.load_card();a.fun.set('Àudio');a.on_function_selected()
            self.assertTrue(a.audio_settings_window.winfo_exists())
            a.audio_duration.set(0)
            with patch.object(m.messagebox,'showerror') as error:
                self.assertFalse(a.apply_card());error.assert_called_once()
            self.assertNotEqual(a.cards[4]['function'],'Àudio')
            a.audio_duration.set(45.5);a.note.set(60);a.channel.set(2)
            a.audio_control_vars['volume']['enabled'].set(True)
            a.audio_control_vars['volume']['min'].set(30)
            a.audio_control_vars['volume']['max'].set(110)
            self.assertTrue(a.apply_card())
            a.activate(4,.5,.5,0);a.deactivate(4)
            self.assertEqual(sum(c.args[0].type=='note_on' for c in a.midi.send.call_args_list),1)
            self.assertIn(4,a.audio_states)
            self.assertEqual(a.assigned_cards['columns'][-1],'audio')
            a.audio_settings_window.destroy()
            with tempfile.TemporaryDirectory() as folder:
                a.project=str(Path(folder)/'project.json');a.save_project()
                a.cards[4]['audio_duration']=1
                with patch.object(m.filedialog,'askopenfilename',return_value=a.project):a.open_project()
                self.assertEqual(a.cards[4]['function'],'Àudio')
                self.assertEqual(a.audio_duration.get(),45.5)
                self.assertTrue(a.audio_control_vars['volume']['enabled'].get())
                self.assertEqual(a.audio_control_vars['volume']['min'].get(),30)
                self.assertEqual(a.audio_control_vars['volume']['max'].get(),110)
                self.assertEqual(a.note.get(),60)
                self.assertEqual(a.channel.get(),2)
            close_test_app(a)
        finally:
            try:root.destroy()
            except m.tk.TclError:pass

    def test_chromatic_live_tracking_stays_out_of_projection_and_recording(self):
        import numpy as np
        root=m.tk.Tk()
        try:
            with patch.object(m.mido,'get_output_names',return_value=[]):a=m.App(root)
            a.arp_stop.set();a.arp_thread.join(timeout=1);root.update()
            a.midi=Mock();a.cards[0]['visual']=12
            for x,y in ((.7,.5),(.6,.4),(.4,.3)):a.activate(0,x,y,0)
            self.assertEqual(len(a.target_trails[0]),3)
            a.open_projection();root.update_idletasks()
            a.display=Mock();a.recording=Mock();a.tick()
            projected=[c.args[1] for c in a.display.call_args_list if c.args[0] is a.proj_label][-1]
            previewed=[c.args[1] for c in a.display.call_args_list if c.args[0] is a.vis_label][-1]
            self.assertTrue(np.all(projected==projected[0,0]))
            self.assertFalse(np.array_equal(projected,previewed))
            np.testing.assert_array_equal(a.recording.write.call_args.args[0],a.last_frame)
            self.assertTrue(a.radial_preview())
            radius=int(min(m.H*.425,m.W*.32))
            self.assertEqual(a.tracking_point(.75,.5,True),(round(m.W/2+radius*.5),m.H//2))
            a.activate(2,.65,.7,.25)
            preview=a.live_preview_frame()
            self.assertEqual(preview.shape,(360,640,3))
            self.assertIn(2,a.target_trails)
            a.deactivate(0);a.deactivate(2);a.tick()
            self.assertFalse(a.last_frame.any());self.assertFalse(a.live_preview_frame().any())
            self.assertFalse(a.target_trails)
            close_test_app(a)
        finally:
            try:root.destroy()
            except m.tk.TclError:pass

    def test_mixer_editor_names_compact_monitor_and_saved_levels(self):
        root=m.tk.Tk()
        try:
            with patch.object(m.mido,'get_output_names',return_value=[]):a=m.App(root)
            a.arp_stop.set();a.arp_thread.join(timeout=1);root.update()
            a.midi=Mock();a.open_mixer();root.update()
            a.midi.send.assert_not_called()
            self.assertIn(0,a.mixer_rows);self.assertIn(2,a.mixer_rows)
            a.card_id.set('01');a.load_card();a.card_name.set('Veu principal')
            self.assertTrue(a.apply_card())
            self.assertEqual(a.cards[0]['name'],'Veu principal')
            self.assertEqual(a.mixer_rows[0]['name'].cget('text'),'Veu principal')
            a.change_mixer_volume(0,64)
            message=a.midi.send.call_args.args[0]
            self.assertEqual((message.type,message.control,message.value),('control_change',20,64))
            self.assertEqual(a.cards[2].get('mixer',{}).get('level',100),100)
            a.change_master_volume(63.5)
            messages=[c.args[0] for c in a.midi.send.call_args_list if c.args[0].type=='control_change']
            self.assertEqual({msg.control:msg.value for msg in messages}[20],32)
            self.assertTrue(all(msg.type!='note_on' for msg in messages))
            a.mixer_rows[2]['variables']['cc'].set(20)
            calls=a.midi.send.call_count
            self.assertFalse(a.send_mixer_volume(2));self.assertEqual(a.midi.send.call_count,calls)
            a.mixer_rows[2]['variables']['cc'].set(22)
            self.assertEqual(tuple(a.assigned_cards['displaycolumns'])[:3],('card','name','function'))
            a.monitor_details.set(True);a.update_monitor_columns()
            self.assertEqual(tuple(a.assigned_cards['displaycolumns']),('#all',))
            a.monitor_details.set(False);a.update_monitor_columns()
            a.show_panel('cards');root.update()
            x,y,w,h=a.assigned_cards.bbox('0','name')
            with patch.object(m.simpledialog,'askstring',return_value='Veu editada'):
                a.edit_card_name(SimpleNamespace(x=x+w//2,y=y+h//2))
            self.assertEqual(a.card_name.get(),'Veu editada')
            with tempfile.TemporaryDirectory() as folder:
                a.project=str(Path(folder)/'project.json');a.save_project()
                a.cards[0]['name']='Temporal';a.master_volume.set(127)
                with patch.object(m.filedialog,'askopenfilename',return_value=a.project):a.open_project()
                self.assertEqual(a.card_name.get(),'Veu editada')
                self.assertEqual(a.master_volume.get(),63.5)
                self.assertEqual(a.mixer_config(0)['level'],64)
            close_test_app(a)
        finally:
            try:root.destroy()
            except m.tk.TclError:pass

if __name__=='__main__':unittest.main()
