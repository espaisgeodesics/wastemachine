import os
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from test_camera import app_module as m

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
            for kind in ('Arpegiador espacial','Patró rítmic'):
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
            with tempfile.TemporaryDirectory() as folder:
                a.project=str(Path(folder)/'project.json');a.save_project()
                a.cards[0]['function']='Cap acció'
                with patch.object(m.filedialog,'askopenfilename',return_value=a.project):a.open_project()
                self.assertEqual(a.cards[0]['function'],'Patró rítmic')
                self.assertEqual(a.cards[0]['arp_direction'],'Descendent')
                self.assertEqual([v.get() for v in a.rhythm_steps],[j in (0,4,8,12) for j in range(16)])
            a.close()
        finally:
            try:root.destroy()
            except m.tk.TclError:pass

if __name__=='__main__':unittest.main()
