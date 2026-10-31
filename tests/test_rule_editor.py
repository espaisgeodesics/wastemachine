import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import time
import threading
import unittest
from unittest.mock import Mock, patch

from domain_events import DomainEvent
from experience_rules import ExperienceRule, RuleAction, RulesConfig
from test_camera import app_module as m


def config(actions=None, trigger='manual'):
    return RulesConfig((ExperienceRule('r','Prova',trigger,actions or (RuleAction('color','#FF0000',duration_s=0),)),))


@unittest.skipUnless(os.environ.get('DISPLAY') or os.name=='nt','Requires a graphical display')
class RuleIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.root=m.tk.Tk()
        with patch.object(m.mido,'get_output_names',return_value=[]):self.app=m.App(self.root)
        self.app.arp_stop.set();self.app.arp_thread.join(timeout=1)
        self.folder=TemporaryDirectory();self.addCleanup(self.folder.cleanup)

    def tearDown(self):
        if self.app.rules_window is not None:
            self.app.rules_window.destroy();self.app.rules_window=None;self.app.rules_editor=None
        if self.app.simulator_window is not None:
            self.app.simulator_window.destroy();self.app.simulator_window=None;self.app.simulator_view=None
        for timer in self.root.tk.call('after','info'):self.root.after_cancel(timer)
        self.app.close()

    def test_manual_rule_real_outputs_override_and_release_to_legacy_frame(self):
        self.app.configure_rules(config())
        before=self.app.compose_output_frame(1).copy()
        self.app.manual_rule('r')
        actual=self.app.compose_output_frame(1)
        m.np.testing.assert_array_equal(actual[0,0],[0,0,255])
        self.app.release_rule_visuals()
        m.np.testing.assert_array_equal(self.app.compose_output_frame(1),before)

    def test_event_rules_deferred_once_until_legacy_pass_finishes(self):
        from marker_tracking import ObservationFrame, MarkerObservation
        self.app.configure_rules(config((RuleAction('note',channel=16,number=65,duration_s=.2),),trigger='marker_appeared'))
        self.app.midi=Mock()
        self.app.update_common_tracking(ObservationFrame('camera:0',1,1,(MarkerObservation(0,(.5,.5),0),)))
        self.app.midi.send.assert_not_called()
        self.app.process_rule_actions(1)
        self.assertEqual(self.app.midi.send.call_args.args[0].type,'note_on')
        self.app.process_rule_actions(1.1)
        self.assertEqual(self.app.midi.send.call_count,1)
        self.app.process_rule_actions(1.3)
        self.assertEqual(self.app.midi.send.call_args.args[0].type,'note_off')

    def test_reserved_channels_reject_configuration_and_legacy_mixer_change_atomically(self):
        self.app.configure_rules(config((RuleAction('note',channel=16,duration_s=.2),)))
        before=self.app.rule_config
        with self.assertRaises(ValueError):self.app.configure_rules(config((RuleAction('note',channel=1,duration_s=.2),)))
        self.assertEqual(self.app.rule_config,before)
        self.app.open_mixer()
        self.app.mixer_rows[0]['variables']['channel'].set(16)
        old=self.app.cards[0].get('mixer')
        with self.assertRaises(ValueError):self.app.read_mixer_route(0)
        self.assertEqual(self.app.cards[0].get('mixer'),old)

    def test_card_apply_cannot_take_reserved_rule_channel(self):
        self.app.configure_rules(config((RuleAction('note',channel=16,duration_s=.2),)))
        self.app.channel.set(16);before=json.loads(json.dumps(self.app.cards))
        with patch.object(m.messagebox,'showerror') as error:self.assertFalse(self.app.apply_card())
        error.assert_called_once();self.assertEqual(self.app.cards,before)

    def test_panic_and_camera_close_release_rule_notes_and_mute_prevents_new_ones(self):
        self.app.configure_rules(config((RuleAction('note',channel=16,duration_s=10),)))
        port=self.app.midi=Mock();self.app.manual_rule('r')
        self.app.toggle_panic()
        self.assertFalse(self.app.rule_outputs.notes)
        self.assertIn('note_off',[c.args[0].type for c in port.send.call_args_list])
        count=port.send.call_count;self.app.manual_rule('r')
        self.assertEqual(port.send.call_count,count)
        self.app.toggle_panic();self.app.manual_rule('r')
        self.app.camera=Mock();self.app.toggle_cam()
        self.assertFalse(self.app.rule_outputs.notes)

    def test_multi_action_form_saves_and_executes_without_sending_on_apply(self):
        self.app.open_rules();editor=self.app.rules_editor;port=self.app.midi=Mock()
        editor.fields['name'].set('Color i nota');editor.fields['trigger'].set('Ordre manual')
        editor.af['value'].set('#00FF00');editor.put_action(False)
        editor.af['kind'].set('Nota MIDI');editor.af['duration_s'].set('.2');editor.put_action(False)
        self.assertTrue(editor.apply_rule());port.send.assert_not_called()
        self.assertEqual(len(self.app.rule_config.rules[0].actions),2)
        editor.execute()
        self.assertEqual(port.send.call_args.args[0].type,'note_on')
        m.np.testing.assert_array_equal(self.app.compose_output_frame(1)[0,0],[0,255,0])

    def test_pending_action_and_form_block_silent_save(self):
        self.app.open_rules();editor=self.app.rules_editor
        editor.fields['name'].set('Pendent');editor.af['value'].set('#00FF00')
        with patch('rule_editor.messagebox.showerror') as error:self.assertFalse(editor.apply_rule())
        error.assert_called_once()
        with patch.object(m.messagebox,'showwarning') as warning:self.app.save_project()
        warning.assert_called_once();self.assertFalse(self.app.rule_config.rules)

    def save(self,path):
        with patch.object(m.filedialog,'asksaveasfilename',return_value=str(path)):self.app.save_project(True)
        self.assertTrue(path.is_file());return json.loads(path.read_text(encoding='utf-8'))

    def open(self,path):
        with patch.object(m.filedialog,'askopenfilename',return_value=str(path)):self.app.open_project()

    def test_project_roundtrip_old_project_and_invalid_rules_do_not_mutate_current_state(self):
        self.app.configure_rules(config());path=Path(self.folder.name)/'project.json'
        data=self.save(path);self.app.new_project();self.assertFalse(self.app.rule_config.rules)
        self.open(path);self.assertEqual(self.app.rule_config,config())
        bad=Path(self.folder.name)/'bad.json';bad_data=dict(data,experience_rules={'schema_version':99,'rules':[]})
        bad.write_text(json.dumps(bad_data));before=self.app.rule_config;port=self.app.midi=Mock()
        with patch.object(m.messagebox,'showerror') as error:self.open(bad)
        error.assert_called_once();port.send.assert_not_called();self.assertEqual(self.app.rule_config,before)
        data.pop('experience_rules');old=Path(self.folder.name)/'old.json';old.write_text(json.dumps(data))
        self.open(old);self.assertFalse(self.app.rule_config.rules)

    def test_simulator_copies_and_executes_rules_without_touching_real_outputs(self):
        self.app.configure_rules(config((RuleAction('color','#112233',duration_s=0),RuleAction('note',duration_s=.2)),trigger='marker_appeared'))
        port=self.app.midi=Mock();before=self.app.compose_output_frame(1).copy()
        self.app.open_simulator();view=self.app.simulator_view;view.load_zones()
        # Force a new appearance in the isolated simulator, not the real tracker.
        s=self.app.simulator_session;now=time.monotonic()
        s.set_pose('virtual-1',visible=False);s.advance(now+.01)
        s.advance(now+1.1);s.set_pose('virtual-1',visible=True);s.advance(now+1.2)
        self.assertIsNotNone(s.rule_outputs.frame((10,10)))
        self.assertTrue(s.midi_commands)
        port.send.assert_not_called()
        m.np.testing.assert_array_equal(self.app.compose_output_frame(1),before)
        self.assertFalse(self.app.rule_outputs.claims)

    def test_missing_image_keeps_existing_public_output_and_logs_diagnostic(self):
        self.app.configure_rules(config());self.app.manual_rule('r')
        before=self.app.compose_output_frame(1).copy()
        # A second rule fails to load; applying that action cannot replace the accepted visual.
        failing=ExperienceRule('missing','Inexistent','manual',(RuleAction('image','missing.png',duration_s=0),),priority=100)
        requests=m.RuleEngine(RulesConfig((failing,))).manual('missing',1)
        self.app.rule_outputs.apply(requests,1,project_file=Path(self.folder.name)/'p.json')
        m.np.testing.assert_array_equal(self.app.compose_output_frame(1),before)
        self.assertNotEqual(self.app.rule_outputs.log[-1][3],'acceptada')

    def test_editor_close_cancels_its_timer(self):
        self.app.open_rules();timer=self.app.rules_editor.timer;window=self.app.rules_window
        window.tk.call(window.protocol('WM_DELETE_WINDOW'))
        self.assertIsNone(self.app.rules_editor)
        self.assertNotIn(timer,self.root.tk.call('after','info'))

    def test_failed_project_write_leaves_previous_json_intact(self):
        path=Path(self.folder.name)/'project.json';self.save(path)
        before=path.read_bytes()
        self.app.configure_rules(config())
        with patch.object(m.json,'dump',side_effect=OSError('disk full')),patch.object(m.messagebox,'showerror') as error:
            self.app.save_project()
        error.assert_called_once();self.assertEqual(path.read_bytes(),before)
        self.assertFalse(list(path.parent.glob('*.tmp')))

    def test_editing_one_action_preserves_other_actions(self):
        actions=(RuleAction('color','#FF0000',duration_s=0),RuleAction('note',duration_s=.2))
        self.app.configure_rules(config(actions));self.app.open_rules();editor=self.app.rules_editor
        editor.table.selection_set('r');editor.select()
        editor.action_table.selection_set('0');editor.select_action()
        editor.af['value'].set('#0000FF');editor.put_action(True)
        self.assertTrue(editor.apply_rule())
        self.assertEqual(self.app.rule_config.rules[0].actions[1],actions[1])
        self.assertEqual(self.app.rule_config.rules[0].actions[0].value,'#0000FF')

    def test_rule_note_deadline_runs_on_music_thread_without_tk_updates(self):
        self.app.configure_rules(config((RuleAction('note',duration_s=.05),)))
        done=threading.Event();port=self.app.midi=Mock()
        port.send.side_effect=lambda message:done.set() if message.type=='note_off' else None
        self.app.manual_rule('r')
        self.app.arp_stop=threading.Event();self.app.arp_thread=threading.Thread(target=self.app.arpeggio_worker,daemon=True)
        self.app.arp_thread.start()
        self.assertTrue(done.wait(1),'No note-off while Tk thread was blocked')
        with self.app.rule_outputs.lock:self.assertFalse(self.app.rule_outputs.notes)

    def test_rule_image_save_as_keeps_resource_identity_and_reloads_correct_file(self):
        from PIL import Image
        root=Path(self.folder.name);old=root/'old';new=root/'new';old.mkdir();new.mkdir()
        image=old/'photo.png';Image.new('RGB',(20,20),'lime').save(image)
        self.app.project=str(old/'p.json')
        self.app.configure_rules(config((RuleAction('image','photo.png',duration_s=0),)))
        self.save(new/'p.json')
        self.app.rule_outputs.store.clear();self.app.manual_rule('r')
        m.np.testing.assert_array_equal(self.app.compose_output_frame(1)[m.H//2,m.W//2],[0,255,0])
        self.assertEqual(self.app.rule_outputs.winner().image.path,image)

    def test_real_detector_to_rules_keeps_legacy_notes_and_deduplicates_rule_midi(self):
        from spatial_zones import SpatialMap, Zone, Calibration
        from PIL import Image
        image_path=Path(self.folder.name)/'green.png';Image.new('RGB',(20,20),'lime').save(image_path)
        cells={(r,c) for r in range(8) for c in range(8) if self.app.spatial_map.grid.eligible((r,c))}
        self.app.apply_spatial_map(SpatialMap(zones=(Zone('z','Bosc',cells,set(range(5))),),
                                            calibration=Calibration(((.5,0),(1,.5),(.5,1),(0,.5)))))
        actions=(RuleAction('image',str(image_path),duration_s=0),RuleAction('note',number=70,duration_s=.2),RuleAction('cc','99',number=74))
        self.app.configure_rules(config(actions,trigger='zone_entered'))
        for i in range(5):self.app.cards[i].update(function='Nota MIDI',channel=1,note=60+i,visual=0)
        image=m.np.full((300,900),255,m.np.uint8)
        dictionary=m.cv2.aruco.getPredefinedDictionary(m.cv2.aruco.DICT_4X4_50)
        for i in range(5):image[80:180,20+i*175:120+i*175]=m.cv2.aruco.generateImageMarker(dictionary,i,100)
        image=m.cv2.cvtColor(image,m.cv2.COLOR_GRAY2BGR)
        self.app.camera=Mock();self.app.camera.read.side_effect=lambda:(True,image.copy())
        port=self.app.midi=Mock();self.app.display=Mock();self.app.t0=0;self.app.clock_start=0
        for now in (10,10.08,10.16,10.24,10.4):
            with patch.object(m.time,'monotonic',return_value=now):self.app.tick()
        messages=[call.args[0] for call in port.send.call_args_list]
        self.assertEqual(len([msg for msg in messages if msg.type=='note_on' and msg.channel==0]),5)
        self.assertEqual(len([msg for msg in messages if msg.type=='note_on' and msg.channel==15]),1)
        self.assertEqual(len([msg for msg in messages if msg.type=='note_off' and msg.channel==15]),1)
        self.assertEqual(len([msg for msg in messages if msg.type=='control_change' and msg.control==74]),1)
        m.np.testing.assert_array_equal(self.app.last_frame[m.H//2,m.W//2],[0,255,0])


if __name__=='__main__':unittest.main()
