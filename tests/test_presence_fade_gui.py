import json,os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock,patch
from test_camera import app_module as module

@unittest.skipUnless(os.name=='nt' or os.environ.get('DISPLAY'),'Requires graphical display')
class PresenceFadeGuiTests(unittest.TestCase):
    def setUp(self):
        self.root=module.tk.Tk();self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        with patch.object(module.mido,'get_output_names',return_value=[]):self.app=module.App(self.root)
        self.app.arp_stop.set();self.app.arp_thread.join(1)
        self.errors=[];self.root.report_callback_exception=lambda typ,value,tb:self.errors.append(str(value))
        self.app.fun.set(module.MUTE_FUNCTION);self.app.open_mute_settings()
    def tearDown(self):
        self.app.confirm_rule_discard=lambda:True;self.app.confirm_zone_discard=lambda:True
        self.app.close()
    def enable(self):
        self.app.mute_fade_enabled.set(True)
        self.assertTrue(self.app.apply_card())
    def attach(self):
        output=Mock();self.app.midi=output;return output
    def at(self,now,action):
        with patch.object(module.time,'monotonic',return_value=now):return action()
    def values(self,output):
        return [(c.args[0].type,c.args[0].channel,c.args[0].control,c.args[0].value) for c in output.send.call_args_list]
    def test_apply_save_reload_keeps_explicit_times_and_does_not_touch_other_cards(self):
        other=json.dumps(self.app.cards[1:])
        self.app.mute_fade_enabled.set(True);self.app.mute_fade_in.set('2,5');self.app.mute_fade_out.set('4');self.app.mute_fade_level.set(90)
        self.assertTrue(self.app.apply_card());self.assertEqual(json.dumps(self.app.cards[1:]),other)
        path=Path(self.temp.name)/'fade.json'
        with patch.object(module.filedialog,'asksaveasfilename',return_value=str(path)):self.assertTrue(self.app.save_project(True))
        self.assertTrue(self.app.load_project_file(path))
        self.assertEqual(self.app.cards[0]['mute_fade'],dict(enabled=True,cc=118,in_s=2.5,out_s=4.,level=90))
        self.assertEqual(self.app.mute_fade_out.get(),'4.0');self.assertTrue(self.app.mute_fade_enabled.get())
        self.assertFalse(self.errors)
    def test_real_detection_fades_and_reverses_using_only_cc_messages(self):
        self.enable();output=self.attach()
        self.at(10,lambda:self.app.activate(0,.5,.5,0))
        self.assertEqual(self.values(output),[('control_change',0,118,0),('control_change',0,119,0)])
        self.at(11.5,self.app.sync_mute_controls)
        self.assertEqual(self.values(output)[-1],('control_change',0,118,100))
        self.at(12,lambda:self.app.deactivate(0))
        self.at(13,self.app.sync_mute_controls)
        self.assertEqual(self.values(output)[-1],('control_change',0,118,50))
        output.send.reset_mock()
        self.at(13,lambda:self.app.activate(0,.5,.5,0));self.at(13.75,self.app.sync_mute_controls)
        self.assertNotIn(('control_change',0,118,0),self.values(output))
        self.assertEqual(self.values(output)[-1],('control_change',0,118,100))
        self.at(14,lambda:self.app.deactivate(0));self.at(16,self.app.sync_mute_controls)
        self.assertEqual(self.values(output)[-2:],[('control_change',0,118,0),('control_change',0,119,127)])
        self.assertTrue(all(m[0]=='control_change' and m[2] in (118,119) for m in self.values(output)))
    def test_panic_is_immediate_and_cancels_pending_fades(self):
        self.enable();output=self.attach()
        self.at(10,lambda:self.app.activate(0,.5,.5,0));self.at(11.5,self.app.sync_mute_controls)
        self.app.muted=True;self.at(11.6,self.app.sync_mute_controls)
        self.assertEqual(self.values(output)[-2:],[('control_change',0,118,0),('control_change',0,119,127)])
        output.send.reset_mock();self.at(20,self.app.sync_mute_controls)
        self.assertFalse(output.send.call_args_list)
    def test_route_send_failure_rejects_edits_without_mutating_project(self):
        self.enable();output=self.attach()
        self.at(10,lambda:self.app.activate(0,.5,.5,0));self.at(11.5,self.app.sync_mute_controls)
        original=json.dumps(self.app.cards);self.app.channel.set(2);output.send.side_effect=OSError('port unavailable')
        with patch.object(module.messagebox,'showerror') as error:
            self.assertFalse(self.at(12,self.app.apply_card))
        self.assertEqual(json.dumps(self.app.cards),original);error.assert_called_once()
    def test_switching_function_silences_old_fade_and_forgets_envelope(self):
        self.enable();output=self.attach()
        self.at(10,lambda:self.app.activate(0,.5,.5,0));self.at(11.5,self.app.sync_mute_controls)
        output.send.reset_mock();self.app.fun.set('Nota MIDI')
        self.assertTrue(self.at(12,self.app.apply_card))
        self.assertEqual(self.values(output)[:2],[('control_change',0,118,0),('control_change',0,119,127)])
        self.assertNotIn(0,self.app.presence_fades.states)
        self.assertNotIn('mute_fade',self.app.cards[0])
        output.send.reset_mock();self.at(30,self.app.sync_mute_controls)
        self.assertFalse(output.send.call_args_list)
    def test_disabling_fade_restores_level_while_muted_before_binary_unmute(self):
        self.enable();output=self.attach()
        self.at(10,lambda:self.app.activate(0,.5,.5,0));self.at(11.5,self.app.sync_mute_controls)
        output.send.reset_mock();self.app.mute_fade_enabled.set(False)
        self.assertTrue(self.at(12,self.app.apply_card))
        self.assertEqual(self.values(output),[('control_change',0,118,0),('control_change',0,119,127),('control_change',0,118,100),('control_change',0,119,0)])
        self.assertNotIn(0,self.app.presence_fades.states)
        self.assertFalse(self.app.cards[0]['mute_fade']['enabled'])

    def test_loading_invalid_fade_does_not_replace_current_project(self):
        self.enable();original=json.dumps(self.app.cards)
        data=dict(version=4,cards=json.loads(original));data['cards'][0]['mute_fade']['cc']=119
        path=Path(self.temp.name)/'invalid.json';path.write_text(json.dumps(data))
        output=self.attach()
        with patch.object(module.messagebox,'showerror') as error:self.assertFalse(self.app.load_project_file(path))
        self.assertEqual(json.dumps(self.app.cards),original);self.assertFalse(output.send.call_args_list);error.assert_called_once()
    def test_legacy_card_stays_binary_until_checkbox_is_enabled(self):
        self.assertFalse(self.app.mute_fade_enabled.get());self.assertTrue(self.app.apply_card())
        output=self.attach();self.app.mute_sent.clear()
        self.at(10,self.app.sync_mute_controls);self.at(11,lambda:self.app.activate(0,.5,.5,0));self.at(12,lambda:self.app.deactivate(0))
        self.assertEqual(self.values(output),[('control_change',0,119,v) for v in (127,0,127)])
    def test_stale_mute_dialog_does_not_apply_a_different_function(self):
        def children(w):
            for c in w.winfo_children():yield c;yield from children(c)
        button=next(w for w in children(self.app.mute_settings_window) if w.winfo_class()=='TButton' and w.cget('text')=='APLICAR A LA TARGETA I TANCAR')
        before=json.dumps(self.app.cards);self.app.fun.set('Nota MIDI')
        with patch.object(module.messagebox,'showerror') as error:button.invoke()
        error.assert_called_once();self.assertEqual(json.dumps(self.app.cards),before)

    def test_apply_footer_remains_visible_at_high_dpi(self):
        def children(w):
            for c in w.winfo_children():yield c;yield from children(c)
        for scale in (1,1.25,1.5):
            self.root.tk.call('tk','scaling',96/72*scale);self.app.open_mute_settings();win=self.app.mute_settings_window
            self.root.update()
            button=next(w for w in children(win) if w.winfo_class()=='TButton' and w.cget('text')=='APLICAR A LA TARGETA I TANCAR')
            self.assertTrue(button.winfo_ismapped())
            self.assertLessEqual(button.winfo_rooty()+button.winfo_height(),win.winfo_rooty()+win.winfo_height())
        self.assertFalse(self.errors)
