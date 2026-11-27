"""Project navigation releases the previous session and restores local layouts."""
import importlib
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from atmo_primary import primary_engine
from test_camera import app_module as engine


class HomeLoopTests(unittest.TestCase):
    def test_new_session_returns_to_universe_without_recursive_windows(self):
        entry=importlib.import_module('atmo_esfera_fx_integracio_19')
        choices=[dict(mode='Música',game_action='new'),dict(mode='Exposició',game_action='open')]
        with patch.object(entry,'choose_experience',side_effect=choices) as choose,patch.object(entry,'open_engine',side_effect=[True,False]) as opened:
            entry.main()
        self.assertEqual(choose.call_count,2)
        self.assertEqual(opened.call_args_list[0].args,('Música','new'))
        self.assertEqual(opened.call_args_list[1].args,('Exposició','open'))


@unittest.skipUnless(os.name=='nt' or os.environ.get('DISPLAY'),'Requires graphical display')
class NavigationTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=engine.tk.Tk();self.root.withdraw()
        with patch.object(engine.mido,'get_output_names',return_value=[]):
            self.app=primary_engine(engine,'Música')(self.root)
        self.app.window_layout_file=Path(self.temp.name)/'layout.json'
        self.app.navigate_new_project=True

    def tearDown(self):
        if not self.app._closing:
            with patch.object(self.app,'confirm_rule_discard',return_value=True),patch.object(self.app,'confirm_zone_discard',return_value=True):self.app.close()

    def test_no_layout_keeps_tools_closed(self):
        self.app.finish_startup()
        self.assertEqual(self.app.visual_window.state(),'withdrawn')

    def test_saved_layout_restores_geometry_and_visibility_on_start(self):
        layout={'layout_version':4,'main':'900x650+15+15','main_state':'normal','panels':{
            'visual':{'geometry':'510x340+40+60','visible':True},
            'camera':{'geometry':'420x300+60+80','visible':False}}}
        self.app.window_layout_file.write_text(json.dumps(layout))
        self.app.finish_startup();self.root.update_idletasks()
        self.assertEqual(self.app.visual_window.state(),'normal')
        self.assertEqual(self.app.camera_window.state(),'withdrawn')
        self.assertEqual(self.app.visual_window.winfo_width(),510)
        self.assertEqual(self.app.visual_window.winfo_height(),340)
        self.assertEqual(json.loads(self.app.window_layout_file.read_text()),layout)

    def test_broken_layout_preserves_hidden_defaults_and_reports_error(self):
        self.app.window_layout_file.write_text('{invalid')
        self.app.finish_startup()
        self.assertEqual(self.app.visual_window.state(),'withdrawn')
        self.assertIn('No s’ha pogut recuperar',self.app.status.get())

    def test_cancel_or_failed_save_keeps_current_session(self):
        self.app.finish_startup()
        with patch.object(self.app,'confirm_new_project',return_value=False):self.app.new_project()
        self.assertFalse(self.app.return_to_start)
        self.assertFalse(self.app._closing)
        self.assertTrue(self.root.winfo_exists())

    def test_accepted_new_project_releases_resources_and_requests_home(self):
        self.app.finish_startup()
        with patch.object(self.app,'confirm_new_project',return_value=True),patch.object(self.app,'confirm_rule_discard',return_value=True),patch.object(self.app,'confirm_participant_discard',return_value=True),patch.object(self.app,'confirm_zone_discard',return_value=True):self.app.new_project()
        self.assertTrue(self.app.return_to_start)
        self.assertTrue(self.app._closing)
        self.assertFalse(self.app.arp_thread.is_alive())
        self.assertFalse(self.root.tk.call('after','info'))


if __name__=='__main__':unittest.main()
