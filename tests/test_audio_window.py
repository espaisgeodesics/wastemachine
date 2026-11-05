import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import Mock,patch

from experience_rules import ExperienceRule,RuleAction,RulesConfig
from local_audio import SilentAudioBackend
from test_camera import app_module as m
from test_local_audio import wav,wait_until


@unittest.skipUnless(os.environ.get('DISPLAY') or os.name=='nt','Requires a graphical display')
class LocalAudioIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.root=m.tk.Tk()
        with patch.object(m.mido,'get_output_names',return_value=[]):self.app=m.App(self.root)
        self.app.arp_stop.set();self.app.arp_thread.join(timeout=1)
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=wav(Path(self.temp.name)/'clip.wav',seconds=2)
        self.app.local_audio.factory=SilentAudioBackend

    def tearDown(self):
        for attr,view in (('audio_window','audio_view'),('rules_window','rules_editor'),('simulator_window','simulator_view')):
            window=getattr(self.app,attr)
            if window is not None:window.destroy();setattr(self.app,attr,None);setattr(self.app,view,None)
        for timer in self.root.tk.call('after','info'):self.root.after_cancel(timer)
        self.app.close()

    def enable(self):
        self.app.local_audio.enable()
        self.assertTrue(wait_until(lambda:self.app.local_audio.snapshot().state=='ready'))

    def rule(self):
        return RulesConfig((ExperienceRule('sound','Clip local','manual',
            (RuleAction('play_sound',str(self.path),loop=True,gain=.6,fade_s=0),),group='birds'),))

    def start(self):
        self.app.configure_rules(self.rule());self.enable();self.app.manual_rule('sound')
        self.assertTrue(wait_until(lambda:len(self.app.local_audio.snapshot().voices)==1))

    def test_opening_panel_or_project_never_activates_device(self):
        self.app.open_local_audio()
        self.assertIsNone(self.app.local_audio.thread)
        self.app.configure_rules(self.rule());self.app.manual_rule('sound')
        self.assertIsNone(self.app.local_audio.thread)
        self.assertFalse(self.app.local_audio.snapshot().voices)
        self.assertIn('no activat',self.app.rule_outputs.log[-1][3])

    def test_local_rule_and_stop_only_local_leave_midi_and_legacy_notes_untouched(self):
        port=self.app.midi=Mock();self.app.notes[0]=(0,60)
        self.start();port.send.assert_not_called()
        self.app.stop_local_audio()
        self.assertTrue(wait_until(lambda:not self.app.local_audio.snapshot().voices))
        port.send.assert_not_called();self.assertEqual(self.app.notes,{0:(0,60)})

    def test_master_and_selected_layer_controls_show_actual_snapshot(self):
        self.start();self.app.open_local_audio();view=self.app.audio_view
        self.app.local_audio.set_master(.5)
        self.assertTrue(wait_until(lambda:abs(self.app.local_audio.snapshot().voices[0].gain-.3)<.01))
        view.refresh()
        self.assertEqual(view.table.item('0','values')[5],'30')
        view.table.selection_set('0');view.stop_selected()
        self.assertTrue(wait_until(lambda:not self.app.local_audio.snapshot().voices))

    def test_panic_camera_close_and_rule_reconfiguration_stop_local_voices(self):
        self.start();self.app.toggle_panic()
        self.assertTrue(wait_until(lambda:not self.app.local_audio.snapshot().voices))
        self.app.manual_rule('sound');self.assertFalse(self.app.local_audio.snapshot().voices)
        self.app.toggle_panic();self.app.manual_rule('sound')
        self.assertTrue(wait_until(lambda:bool(self.app.local_audio.snapshot().voices)))
        self.app.camera=Mock();self.app.toggle_cam()
        self.assertTrue(wait_until(lambda:not self.app.local_audio.snapshot().voices))
        self.app.manual_rule('sound');self.assertTrue(wait_until(lambda:bool(self.app.local_audio.snapshot().voices)))
        self.app.configure_rules(RulesConfig())
        self.assertTrue(wait_until(lambda:not self.app.local_audio.snapshot().voices))

    def test_sound_form_group_volume_fade_loop_and_schema_two_roundtrip(self):
        self.app.open_rules();editor=self.app.rules_editor
        editor.fields['name'].set('Ocells');editor.fields['trigger'].set('Ordre manual')
        editor.af['kind'].set('Reproduir so local');editor.af['value'].set(str(self.path))
        editor.af['audio_group'].set('ocells');editor.af['gain'].set('.7');editor.af['fade_s'].set('.4');editor.af['loop'].set('Sí')
        editor.put_action(False);self.assertTrue(editor.apply_rule())
        action=self.app.rule_config.rules[0].actions[0]
        self.assertEqual((action.audio_group,action.gain,action.fade_s,action.loop),('ocells',.7,.4,True))
        path=Path(self.temp.name)/'p.json'
        with patch.object(m.filedialog,'asksaveasfilename',return_value=str(path)):self.app.save_project(True)
        data=json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(data['experience_rules']['schema_version'],2)
        self.assertNotIn('local_audio',data)
        self.app.new_project();self.assertTrue(self.app.load_project_file(path))
        self.assertEqual(self.app.rule_config.rules[0].actions[0].gain,.7)
        self.assertIsNone(self.app.local_audio.thread)

    def test_create_bosc_new_folder_opens_virtual_test_without_optional_packages(self):
        port=self.app.midi=Mock()
        with patch.dict('sys.modules',{'pygame':None,'soundfile':None}),patch.object(m.messagebox,'askyesno',return_value=True),patch.object(m.filedialog,'askdirectory',return_value=self.temp.name):
            self.app.create_bosc_demo()
            s=self.app.simulator_session;now=time.monotonic()
            for delta in (.01,.11,.21):s.advance(now+delta)
        self.assertTrue((Path(self.temp.name)/'BOSC_VIU_PROVA'/'BOSC_VIU_PROVA.json').is_file())
        self.assertTrue(s.audio.snapshot())
        self.assertIsNone(self.app.local_audio.thread)
        port.send.assert_not_called()
        self.assertFalse(self.app.rule_outputs.claims)

    def test_invalid_audio_rules_do_not_stop_current_playback_or_mutate_project(self):
        self.start();before=self.app.rule_config
        data={'cards':self.app.cards,'experience_rules':{'schema_version':99,'rules':[]}}
        path=Path(self.temp.name)/'bad.json';path.write_text(json.dumps(data))
        with patch.object(m.messagebox,'showerror') as error:self.assertFalse(self.app.load_project_file(path))
        error.assert_called_once();self.assertEqual(self.app.rule_config,before)
        self.assertEqual(len(self.app.local_audio.snapshot().voices),1)

    def test_audio_panel_close_cancels_ui_timer_and_keeps_explicit_playback(self):
        self.start();self.app.open_local_audio();timer=self.app.audio_view.timer;window=self.app.audio_window
        window.tk.call(window.protocol('WM_DELETE_WINDOW'))
        self.assertIsNone(self.app.audio_view)
        self.assertNotIn(timer,self.root.tk.call('after','info'))
        self.assertTrue(self.app.local_audio.snapshot().voices)


if __name__=='__main__':unittest.main()
