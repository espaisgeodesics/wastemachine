import importlib.util
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import patch
from local_audio import AudioEngine,AudioCommand,PygameAudioBackend,SilentAudioBackend,inspect_clip
from audio_controller import AudioController
from zone_audio import ZoneAudioPlayer
from spatial_zones import SpatialMap,Zone,Calibration,Stabilization
from test_local_audio import wav,wait_until

@unittest.skipUnless(importlib.util.find_spec('pygame') and importlib.util.find_spec('soundfile'),'SDL and soundfile required')
class SongTests(unittest.TestCase):
    def setUp(self):
        driver=patch.dict(os.environ,{'SDL_AUDIODRIVER':'dummy'});driver.start();self.addCleanup(driver.stop)
        self.folder=TemporaryDirectory();self.addCleanup(self.folder.cleanup);self.root=Path(self.folder.name)
        self.song=wav(self.root/'song.wav',seconds=35,rate=8000)
        self.backend=PygameAudioBackend();self.addCleanup(self.backend.close)
    def test_long_wav_uses_bounded_streams_on_independent_channels(self):
        engine=AudioEngine(self.backend);now=time.monotonic()
        for i in range(2):engine.dispatch(AudioCommand('play_sound',f'zone:{i}','test',i,str(self.song),loop=True,fade_s=.1),now)
        self.assertEqual(len(self.backend.streams),2)
        self.assertTrue(all(v.clip.streamed for v in engine.voices.values()))
        self.assertLessEqual(self.backend.cache_bytes,32*1048576)
        until=time.monotonic()+.65
        while time.monotonic()<until:engine.tick(time.monotonic());time.sleep(.01)
        self.assertEqual(len(engine.snapshot()),2)
        self.assertTrue(all(state['file'].tell()>=8000 for state in self.backend.streams.values()))
        engine.dispatch(AudioCommand('stop_sound','zone:0','test',0),time.monotonic())
        self.assertEqual(len(self.backend.streams),1)
        engine.close();self.assertFalse(self.backend.streams)
    def test_stream_loop_eof_and_float_wav_decode(self):
        path=self.root/'float.wav'
        import numpy as np
        self.backend.sf.write(path,np.full((400,2),.2),8000,subtype='FLOAT')
        self.assertGreater(inspect_clip(path)[2],0)
        with patch('local_audio.SHORT_CLIP_S',.01):clip=self.backend.load(path)
        self.assertTrue(clip.streamed)
        self.backend.start(clip,0,True,time.monotonic())
        self.backend.pg.mixer.Channel(0).stop()
        self.assertTrue(self.backend.busy(0,time.monotonic()))
        end=time.monotonic()+.2
        while time.monotonic()<end:self.assertTrue(self.backend.busy(0,time.monotonic()));time.sleep(.01)
        self.backend.stop(0);self.backend.start(clip,0,False,time.monotonic())
        self.assertTrue(wait_until(lambda:not self.backend.busy(0,time.monotonic()),1))
        self.assertFalse(self.backend.streams)
    def test_zone_presence_reaches_real_sdl_even_when_device_starts_later(self):
        self.backend.close()
        controller=AudioController();self.addCleanup(controller.close)
        zone=Zone('song','Cançó',{(3,3)},{0},audio_path=str(self.song),audio_fade_in_s=0)
        points=((.5,0),(1,.5),(.5,1),(0,.5))
        config=SpatialMap(zones=(zone,),calibration=Calibration(points),stabilization=Stabilization(0,0,1,0))
        player=ZoneAudioPlayer(controller);player.configure(config)
        player.update({0:(.45,.45)},0)
        self.assertIn('song',player.pending_starts);self.assertIn('Activa',player.last_error)
        controller.enable();self.assertTrue(wait_until(lambda:controller.snapshot().state=='ready'))
        player.update({0:(.45,.45)},.1)
        self.assertTrue(wait_until(lambda:len(controller.snapshot().voices)==1))
        self.assertEqual(controller.snapshot().voices[0].group,'zone:song')
        self.assertTrue(controller.engine.backend.streams)
        player.update({},.2);player.stop();controller.stop_all()
        self.assertTrue(wait_until(lambda:not controller.snapshot().voices))

if __name__=='__main__':unittest.main()
