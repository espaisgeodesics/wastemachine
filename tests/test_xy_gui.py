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
        self.view=self.app.kaoss_editor;self.view.load_bus_profile()
    def tearDown(self):
        for name in ('confirm_rule_discard','confirm_zone_discard'):setattr(self.app,name,lambda:True)
        self.app.close()
    def test_manual_xy_messages_are_independent_and_project_roundtrip_keeps_settings(self):
        output=Mock()
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
    def test_loading_profile_keeps_custom_port_and_explicit_main_selection(self):
        self.view.port.set('Atmosfera FX2');self.view.load_bus_profile()
        self.assertEqual(self.view.port.get(),'Atmosfera FX2')
        self.assertTrue(self.view.apply())
        self.assertEqual(self.app.cards[0]['kaoss_bus']['port'],'Atmosfera FX2')
        self.view.load_preset();self.assertEqual(self.view.port.get(),'Atmosfera FX2')
        self.view.port.set('');self.view.load_bus_profile()
        self.assertEqual(self.view.port.get(),'')

    def test_main_can_connect_after_xy_already_opened_the_same_windows_endpoint(self):
        own=Mock();own.name='Atmosfera FX2';own.closed=False
        main=Mock();main.name='Atmosfera FX2';main.closed=False
        self.view.port.set('Atmosfera FX2')
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
