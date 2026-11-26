"""Regression coverage for simultaneous music, visuals and camera failures."""
import os,time,json
from threading import Event
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock,patch
import numpy as np
from PIL import Image
from test_camera import app_module as m
from atmo_camera import CameraStream,CameraSnapshot
from atmo_primary import primary_engine

@unittest.skipUnless(os.name=='nt' or os.environ.get('DISPLAY'),'Requires graphical display')
class LiveStabilityTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=m.tk.Tk()
        with patch.object(m.mido,'get_output_names',return_value=[]):self.app=primary_engine(m,'Música')(self.root)
        self.app.window_layout_file=Path(self.temp.name)/'windows.json'
        self.app.finish_startup();self.app.arp_stop.set();self.app.arp_thread.join(1)
        self.errors=[];self.root.report_callback_exception=lambda typ,value,tb:self.errors.append(str(value))
        self.root.update()
    def tearDown(self):
        self.app.confirm_rule_discard=lambda:True;self.app.confirm_zone_discard=lambda:True
        for timer in self.root.tk.call('after','info'):self.root.tk.call('after','cancel',timer)
        self.app.close()
    def generated_mute(self):
        self.app.cards[0].update(function=m.MUTE_FUNCTION,visual=0,channel=1)
        self.app.activate(0,.3,.3,0)
    def test_mute_generated_visual_survives_finished_zone_black(self):
        self.generated_mute();self.app.zone_projection.mode='black'
        self.assertTrue(self.app.compose_output_frame(1).any())
        self.assertTrue(self.app.preview_content_frame(1).any())
        self.app.open_projection();self.root.update()
        self.app.last_frame=self.app.compose_output_frame(1)
        self.assertTrue(self.app.projector_frame().any())
        self.assertEqual(self.app.cards[0]['function'],m.MUTE_FUNCTION)
        self.app.cards[0]['visual']=m.NO_VISUAL
        self.assertFalse(self.app.compose_output_frame(1).any())
    def test_mute_preview_shows_visual_and_edit_invalidates_paused_output(self):
        self.generated_mute()
        self.assertTrue(self.app.card_preview_frame(0,1).any())
        self.app.load_card();self.app.visual_paused=True;self.app.visual_dirty=False;self.app.preview_dirty=False
        self.assertTrue(self.app.apply_card())
        self.assertTrue(self.app.visual_dirty);self.assertTrue(self.app.preview_dirty)
        self.assertEqual(self.app.cards[0]['function'],m.MUTE_FUNCTION)
    def test_mute_photos_keep_independent_players_and_sound_settings(self):
        for i,color in enumerate(('red','blue')):
            path=Path(self.temp.name)/f'{i}.png';Image.new('RGB',(40,40),color).save(path)
            self.app.cards[i].update(function=m.MUTE_FUNCTION,visual=m.MEDIA_VISUAL,channel=i+1,
                media_path=str(path),media_fade_in_s=0,media_fade_out_s=.5)
            self.app.activate(i,.3,.3,0)
        self.app.process_card_media()
        player=self.app.projection_mosaic
        deadline=time.monotonic()+2
        while time.monotonic()<deadline and any(p.decoder.snapshot()[0] is None for p in player.cards.values()):time.sleep(.01)
        frame=player.frame((400,200))
        self.assertEqual(frame[100,100].tolist(),[0,0,255]);self.assertEqual(frame[100,300].tolist(),[255,0,0])
        self.assertEqual([c['function'] for c in self.app.cards[:2]],[m.MUTE_FUNCTION]*2)
    def test_projection_independent_from_main_and_operator_preview(self):
        self.generated_mute();self.app.open_projection();self.root.update()
        self.assertEqual(str(self.app.projection.transient()),'')
        self.app.visual_window.withdraw();self.app.camera_window.withdraw()
        self.app.last_frame=self.app.compose_output_frame(1)
        first=self.app.projector_frame().copy()
        self.app.last_frame=self.app.compose_output_frame(2)
        self.assertFalse(np.array_equal(first,self.app.projector_frame()))
        self.assertEqual(self.app.projection.state(),'normal')
        self.assertFalse(self.errors)
    @unittest.skipUnless(os.name=='nt','Native minimisation requires Windows window manager')
    def test_windows_minimising_main_keeps_projection_mapped(self):
        self.generated_mute();self.app.open_projection();self.root.update()
        self.root.iconify();self.root.update()
        self.assertEqual(self.app.projection.state(),'normal')
        self.assertTrue(self.app.projection.winfo_ismapped())
        self.app.last_frame=self.app.compose_output_frame(2)
        self.assertTrue(self.app.projector_frame().any())
        self.root.deiconify();self.root.update()
    def test_invalid_camera_frame_does_not_block_projector_or_raise_tk_error(self):
        self.generated_mute();self.app.open_projection();self.root.update()
        self.app.camera=Mock();self.app.camera.read.return_value=(True,None)
        self.app.last_seen[0]=time.monotonic()
        with patch.object(self.app,'display',wraps=self.app.display) as display:
            self.app.visual_dirty=True;self.app.tick()
            self.assertTrue(any(c.args[0] is self.app.proj_label for c in display.call_args_list))
        self.assertIn('descartat',self.app.status.get());self.assertFalse(self.errors)
    def test_repeated_camera_snapshot_does_not_keep_old_card_active(self):
        stream=CameraStream(0,0);frame=np.zeros((40,40,3),np.uint8)
        snapshot=CameraSnapshot(frame,1,10.,'ready','',0,1,0,0)
        self.app.camera=stream;stream.snapshot=lambda:snapshot
        self.app.camera_reader_sequence=1;self.app.camera_frame_stamp=10
        self.generated_mute();self.app.last_seen[0]=10
        with patch.object(m.time,'monotonic',return_value=11):self.app.process_camera()
        self.assertNotIn(0,self.app.active)
    def test_blocked_device_read_keeps_tk_and_projector_responsive(self):
        entered=Event();finish=Event()
        capture=Mock();capture.isOpened.return_value=True
        def read():
            entered.set();finish.wait(2);return True,np.zeros((40,40,3),np.uint8)
        capture.read.side_effect=read
        stream=CameraStream(0,0,capture_factory=lambda *_:capture).start()
        try:
            self.assertTrue(entered.wait(1));self.app.camera=stream
            self.generated_mute();self.app.last_seen[0]=time.monotonic()
            self.app.open_projection();self.root.update_idletasks()
            started=time.monotonic()
            with patch.object(self.app,'display',wraps=self.app.display) as display:
                self.app.visual_dirty=True;self.app.tick()
                self.assertTrue(any(c.args[0] is self.app.proj_label for c in display.call_args_list))
            heartbeat=[];self.root.after(0,lambda:heartbeat.append(True));self.root.update()
            self.assertEqual(heartbeat,[True]);self.assertLess(time.monotonic()-started,.5)
            self.assertFalse(self.errors)
        finally:finish.set();stream.release(1);self.app.camera=None
    def test_five_mute_visuals_and_fades_survive_project_roundtrip(self):
        for i in range(5):self.app.cards[i].update(function=m.MUTE_FUNCTION,channel=i+1,cc=119,visual=i,
            mute_fade=dict(enabled=True,cc=118,in_s=1.5,out_s=2.,level=100))
        self.app.load_card()
        expected=[(c['function'],c['channel'],c['cc'],c['visual'],c['mute_fade']) for c in self.app.cards[:5]]
        path=Path(self.temp.name)/'primavera.json'
        with patch.object(m.filedialog,'asksaveasfilename',return_value=str(path)):self.assertTrue(self.app.save_project(True))
        self.assertTrue(self.app.load_project_file(path))
        self.assertEqual([(c['function'],c['channel'],c['cc'],c['visual'],c['mute_fade']) for c in self.app.cards[:5]],expected)

    def test_card7_note_off_cannot_cut_card6_same_pitch_on_different_channel(self):
        output=self.app.midi=Mock()
        self.app.cards[5].update(function='Nota MIDI',channel=6,note=52)
        self.app.cards[6].update(function='Arpegiador espacial',channel=7,note=64)
        self.app.activate(5,.5,.5,0)
        # Exercise the overlapping E3 actually reachable in the arpeggio's outer ring.
        self.app.arp_states[6]={'pitches':[52,56,59,64],'index':0,'last_step':None,'playing':None,'off_at':0}
        self.app.clock_start=10
        for now in (10,10.2,10.3,10.5,10.6,10.8):self.app.sequencer_tick(now)
        self.app.stop_arpeggio(6)
        self.assertEqual(self.app.notes[5],(5,52))
        messages=[c.args[0] for c in output.send.call_args_list]
        self.assertTrue(any(x.type=='note_off' and x.note==52 and x.channel==6 for x in messages))
        self.assertFalse(any(x.type=='note_off' and x.channel==5 for x in messages))
        self.assertFalse(any(x.type in ('reset','control_change') for x in messages))
