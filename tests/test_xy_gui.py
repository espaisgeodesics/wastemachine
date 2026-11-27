import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock,patch

from test_camera import app_module as module
from atmo_card_functions import CHAOS_FUNCTION


@unittest.skipUnless(os.name=='nt' or os.environ.get('DISPLAY'),'Requires graphical display')
class XYGuiTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=module.tk.Tk()
        with patch.object(module.mido,'get_output_names',return_value=[]):self.app=module.App(self.root)
        self.app.arp_stop.set();self.app.arp_thread.join(1)
        self.errors=[];self.root.report_callback_exception=lambda typ,value,tb:self.errors.append(str(value))
        self.app.fun.set(CHAOS_FUNCTION);self.app.open_kaoss_settings()
        self.view=self.app.kaoss_editor;self.view.port.set('ATMO FX');self.view.load_bus_profile()
    def tearDown(self):
        for name in ('confirm_rule_discard','confirm_zone_discard'):setattr(self.app,name,lambda:True)
        self.app.close()
    def test_manual_xy_messages_are_independent_and_project_roundtrip_keeps_settings(self):
        output=Mock()
        self.assertTrue(self.view.apply())
        with patch.object(module.mido,'get_output_names',return_value=['ATMO FX']),patch.object(module.mido,'open_output',return_value=output):
            self.view.test_axis('x',64);self.view.test_axis('y',127)
            messages=[c.args[0] for c in output.send.call_args_list]
            self.assertEqual([(m.type,m.channel,m.control,m.value) for m in messages],[('control_change',15,16,64),('control_change',15,17,127)])
            path=Path(self.temp.name)/'xy.json'
            with patch.object(module.filedialog,'asksaveasfilename',return_value=str(path)):
                self.assertTrue(self.app.save_project(True))
            data=json.loads(path.read_text())
            self.assertEqual(data['cards'][0]['kaoss_bus']['port'],'ATMO FX')
            self.assertEqual(data['cards'][0]['kaoss_bus']['rate_hz'],25)
            self.assertTrue(self.app.load_project_file(path))
            self.assertEqual(self.app.cards[0]['kaoss']['y_cc'],17)
            self.assertEqual(self.app.cards[0]['kaoss_bus']['return_s'],.6)
        self.assertFalse(self.errors)
    def test_probe_never_reapplies_or_sends_volume_on_shared_main_port(self):
        main=Mock();main.name='ATMO FX';main.closed=False
        self.app.midi=module.TracedMidiOutput(main,lambda message,error:None)
        self.assertTrue(self.view.apply())
        main.send.reset_mock()
        with patch.object(self.app,'apply_card',side_effect=AssertionError('A probe must not apply')):
            self.view.test_axis('x',64)
            self.view.test_axis('y',127)
        messages=[call.args[0] for call in main.send.call_args_list]
        self.assertEqual([(m.type,m.channel,m.control,m.value) for m in messages],[('control_change',15,16,64),('control_change',15,17,127)])
        self.assertIn('BF 11 7F',self.view.last_probe)
        self.view.copy_probe()
        self.assertEqual(self.root.clipboard_get(),self.view.last_probe)
        self.assertFalse(self.errors)

    def test_dirty_probe_is_rejected_without_mutating_or_opening_ports(self):
        with patch('atmo_card_functions.messagebox.showerror') as error,patch.object(module.mido,'open_output') as opened:
            self.view.test_axis('x',64)
        error.assert_called_once();opened.assert_not_called()
        self.assertNotEqual(self.app.cards[0]['function'],CHAOS_FUNCTION)
        self.assertTrue(self.view.apply())
        self.view.port.set('Different port')
        with patch('atmo_card_functions.messagebox.showerror') as error,patch.object(module.mido,'open_output') as opened:
            self.view.test_axis('y',64)
        error.assert_called_once();opened.assert_not_called()
        self.assertEqual(self.app.cards[0]['kaoss_bus']['port'],'ATMO FX')
        self.assertFalse(self.errors)

    def test_loading_profile_keeps_custom_port_and_explicit_main_selection(self):
        self.view.port.set('Atmosfera FX2');self.view.load_bus_profile()
        self.assertEqual(self.view.port.get(),'Atmosfera FX2')
        self.assertTrue(self.view.apply())
        self.assertEqual(self.app.cards[0]['kaoss_bus']['port'],'Atmosfera FX2')
        self.view.load_preset();self.assertEqual(self.view.port.get(),'Atmosfera FX2')
        self.view.port.set('');self.view.load_bus_profile()
        self.assertEqual(self.view.port.get(),'')

    def test_cakewalk_selector_roundtrip_and_independent_cards(self):
        from atmo_xy_control import CAKEWALK_PRESETS
        self.assertEqual(tuple(self.view.cakewalk_box['values']),tuple(CAKEWALK_PRESETS))
        for index,name in enumerate(CAKEWALK_PRESETS):
            self.app.card_id.set(str(index+1));self.app.open_kaoss_settings()
            view=self.app.kaoss_editor
            view.port.set('ATMO ESFERA FX 2' if index!=1 else '')
            view.load_bus_profile(name)
            self.assertEqual(view.port.get(),'ATMO ESFERA FX 2' if index!=1 else '')
            self.assertEqual(view.preset_name.get(),name)
            # Reverb/echo share historical CCs: use a distinct channel for echo.
            if index==1:view.channel.set('15')
            self.assertTrue(view.apply())
        path=Path(self.temp.name)/'three-presets.json'
        with patch.object(module.filedialog,'asksaveasfilename',return_value=str(path)):
            self.assertTrue(self.app.save_project(True))
        self.assertTrue(self.app.load_project_file(path))
        for index,name in enumerate(CAKEWALK_PRESETS):
            item=self.app.cards[index]
            self.assertEqual(item['kaoss_ambience'],name)
            self.assertEqual(item['kaoss']['x_cc'],CAKEWALK_PRESETS[name][0])
            self.assertEqual(item['kaoss_neutral']['y'],0)
            self.app.card_id.set(str(index+1));self.app.open_kaoss_settings()
            self.assertEqual(self.app.kaoss_editor.cakewalk_preset.get(),name)
        self.assertFalse(self.errors)

    def test_missing_port_feedback_and_explicit_main_choice_do_not_apply(self):
        self.view.port.set('Missing device')
        with patch.object(module.mido,'get_output_names',return_value=['ATMO ESFERA FX 2']):
            self.view.refresh_ports()
        self.assertIn('no disponible',self.view.port_feedback.get())
        self.assertEqual(self.view.port.get(),'Missing device')
        before=json.dumps(self.app.cards)
        self.view.use_main_output()
        self.assertEqual(self.view.port.get(),'')
        self.assertEqual(json.dumps(self.app.cards),before)
        self.assertTrue(self.view.apply())
        self.assertEqual(self.app.cards[0]['kaoss_bus']['port'],'')

    def test_less_extreme_filter_is_opt_in_and_persisted(self):
        self.assertEqual(self.view.ranges['x'][0].get(),'0')
        before=json.dumps(self.app.cards)
        self.view.limit_filter()
        self.assertEqual(self.view.ranges['x'][0].get(),'60')
        self.assertEqual(json.dumps(self.app.cards),before)
        self.assertTrue(self.view.apply())
        self.assertEqual(self.app.cards[0]['kaoss_ranges']['x'],[60,127])
        self.assertEqual(self.app.cards[0]['kaoss_neutral']['x'],127)
        self.assertEqual(self.app.cards[0]['kaoss']['x_cc'],16)

    def test_main_can_connect_after_xy_already_opened_the_same_windows_endpoint(self):
        own=Mock();own.name='Atmosfera FX2';own.closed=False
        main=Mock();main.name='Atmosfera FX2';main.closed=False
        self.view.port.set('Atmosfera FX2')
        self.assertTrue(self.view.apply())
        with patch.object(module.mido,'get_output_names',return_value=['Atmosfera FX2']),patch.object(module.mido,'open_output',return_value=own):
            self.view.test_axis('x',64)
        self.assertIs(self.app.live_kaoss.output.ports['Atmosfera FX2'],own)
        self.app.midi_choice.set('Atmosfera FX2')
        def open_main(name):
            own.close.assert_called_once()
            return main
        with patch.object(module.mido,'open_output',side_effect=open_main):self.app.connect_midi()
        main.send.reset_mock()
        with patch.object(module.mido,'open_output',side_effect=OSError('duplicate open')) as opened:
            self.view.test_axis('y',64)
        opened.assert_not_called()
        self.assertTrue(any(c.args[0].type=='control_change' and c.args[0].control==17 and c.args[0].value==64 for c in main.send.call_args_list))
        self.assertFalse(self.errors)

    def test_manual_learning_rejects_live_camera_without_sending(self):
        with patch.object(self.app,'camera',Mock()),patch('atmo_card_functions.messagebox.showerror') as error,patch.object(module.mido,'open_output') as opened:
            self.view.test_axis('x',64)
        error.assert_called_once();opened.assert_not_called()

    def test_muted_test_sends_nothing_and_disabled_route_can_be_applied(self):
        self.assertTrue(self.view.apply())
        self.view.bus_enabled.set(False)
        self.assertTrue(self.view.apply())
        self.assertIsNone(self.app.cards[0].get('kaoss_bus'))
        self.assertFalse(self.app.live_kaoss.bus.cards)
        self.app.muted=True
        with patch('atmo_card_functions.messagebox.showerror') as error,patch.object(module.mido,'open_output') as opened:
            self.view.test_axis('x',64)
        error.assert_called_once();opened.assert_not_called()
        self.assertFalse(self.errors)


if __name__=='__main__':unittest.main()
