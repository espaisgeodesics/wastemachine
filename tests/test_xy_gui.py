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
