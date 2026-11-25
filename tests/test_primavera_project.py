import importlib.util,json,os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock,patch

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'experiencies'/'primavera'
spec=importlib.util.spec_from_file_location('crear_primavera',BASE/'crear_primavera.py')
creation=importlib.util.module_from_spec(spec);spec.loader.exec_module(creation)

class PrimaveraFilesTests(unittest.TestCase):
    def test_five_parts_preserve_score_and_have_distinct_instruments(self):
        with TemporaryDirectory() as folder:
            report=creation.generate(folder)
            self.assertEqual(report['musical_tracks'],5)
            self.assertEqual(report['notes_per_track'],[820,705,697,450,501])
            self.assertTrue(report['notes_balanced'])
            self.assertTrue(report['source_notes_and_timing_preserved'])
            self.assertAlmostEqual(report['duration_seconds'],171.391,places=3)

    def test_saved_project_routes_and_arpeggio_are_valid(self):
        from atmo_music import arp_settings,arp_pitches
        from spatial_zones import SpatialMap
        from participants import ParticipantRegistry
        from experience_rules import RulesConfig
        data=json.loads((BASE/'PRIMAVERA_ATMO.json').read_text(encoding='utf-8'))
        SpatialMap.from_project(data);ParticipantRegistry.from_project(data)
        RulesConfig.from_project(data).validate_channels(data['cards'])
        routes={(c['channel'],c['cc']) for c in data['cards'][:5]}
        self.assertEqual(routes,{(i,119) for i in range(1,6)})
        arp=data['cards'][6];arp_settings(arp)
        for sector in range(8):
            for ring in range(3):
                notes=arp_pitches(arp,sector,ring,[52,56,59],{'Major (jònica)':(0,2,4,5,7,9,11)})
                self.assertEqual(len(notes),4)
                self.assertEqual({n%12 for n in notes},{4,8,11})
        self.assertTrue(all(c['visual']==13 for c in data['cards']))
        self.assertTrue(all(c['function']=='Cap acció' for c in data['cards'][7:]))

@unittest.skipUnless(os.name=='nt' or os.environ.get('DISPLAY'),'Requires graphical display')
class PrimaveraAppTests(unittest.TestCase):
    def test_real_app_load_save_and_presence_mute_messages(self):
        from test_camera import app_module as module
        root=module.tk.Tk()
        with patch.object(module.mido,'get_output_names',return_value=[]):app=module.App(root)
        try:
            app.arp_stop.set();app.arp_thread.join(1)
            self.assertTrue(app.load_project_file(BASE/'PRIMAVERA_ATMO.json'))
            output=Mock();app.midi=output;app.muted=False
            app.mute_sent.clear();app.mute_retry_after.clear()
            app.sync_mute_controls()
            sent=[call.args[0] for call in output.send.call_args_list]
            self.assertEqual([(m.type,m.channel,m.control,m.value) for m in sent],[('control_change',i,119,127) for i in range(5)])
            for index in range(5):self.assertTrue(app.send_mute_state(index,True))
            sent=[call.args[0] for call in output.send.call_args_list[-5:]]
            self.assertEqual([(m.channel,m.control,m.value) for m in sent],[(i,119,0) for i in range(5)])
            with TemporaryDirectory() as folder:
                path=Path(folder)/'saved.json'
                with patch.object(module.filedialog,'asksaveasfilename',return_value=str(path)):
                    self.assertTrue(app.save_project(True))
                self.assertTrue(app.load_project_file(path))
                self.assertEqual(app.cards[6]['arp_notes'],[64,68,71,76])
                self.assertEqual(app.cards[5]['note'],52)
        finally:
            app.confirm_rule_discard=lambda:True;app.confirm_zone_discard=lambda:True
            app.close()
