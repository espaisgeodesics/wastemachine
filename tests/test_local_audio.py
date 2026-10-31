import importlib.util
import os
from pathlib import Path
import struct
from tempfile import TemporaryDirectory
import threading
import time
import unittest
from unittest.mock import patch
import wave

from audio_controller import AudioController
from local_audio import AudioCommand, AudioEngine, SilentAudioBackend, PygameAudioBackend, inspect_clip


def wav(path,seconds=.3,rate=22050,channels=1):
    with wave.open(str(path),'wb') as out:
        out.setparams((channels,2,rate,0,'NONE','not compressed'))
        out.writeframes(struct.pack('<h',1000)*round(rate*seconds)*channels)
    return path


def wait_until(predicate,timeout=2):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        if predicate():return True
        threading.Event().wait(.01)
    return bool(predicate())


class AudioEngineTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=wav(Path(self.temp.name)/'clip.wav',seconds=2)
        self.backend=SilentAudioBackend();self.engine=AudioEngine(self.backend)
        self.addCleanup(self.engine.close)

    def play(self,marker=0,group='birds',**kwargs):
        return AudioCommand('play_sound',group,'camera:0',marker,str(self.path),loop=kwargs.pop('loop',True),**kwargs)

    def test_independent_channels_simultaneous_layers_and_natural_completion(self):
        for i in range(5):self.engine.dispatch(self.play(i,loop=False),0)
        self.assertEqual(len(self.engine.snapshot()),5)
        self.assertEqual(len({v.slot for v in self.engine.snapshot()}),5)
        self.assertEqual(len(self.backend.cache),1)
        self.engine.tick(2.1);self.assertFalse(self.engine.snapshot())

    def test_fade_in_marker_volume_group_volume_and_master_multiply(self):
        self.engine.dispatch(self.play(gain=.8,fade_s=1),0)
        self.engine.tick(.5);self.assertAlmostEqual(self.engine.snapshot()[0].gain,.4)
        self.engine.dispatch(AudioCommand('audio_volume','birds',gain=.5,fade_s=1,scope='group'),.5)
        self.engine.master=.5;self.engine.tick(1.5)
        self.assertAlmostEqual(self.engine.snapshot()[0].gain,.8*.5*.5)
        self.engine.dispatch(AudioCommand('audio_volume','birds','camera:0',0,gain=.2),1.6)
        self.assertAlmostEqual(self.engine.snapshot()[0].gain,.2*.5*.5)

    def test_group_stop_and_marker_stop_do_not_affect_other_people_or_groups(self):
        self.engine.dispatch(self.play(0),0);self.engine.dispatch(self.play(1),0);self.engine.dispatch(self.play(2,'wind'),0)
        self.engine.dispatch(AudioCommand('stop_sound','birds','camera:0',0,fade_s=.5),0)
        self.engine.tick(.25)
        self.assertEqual(len(self.engine.snapshot()),3)
        self.engine.tick(.6)
        self.assertEqual({v.marker_id for v in self.engine.snapshot()},{1,2})
        self.engine.dispatch(AudioCommand('stop_sound','birds',scope='group'),.7)
        self.assertEqual([v.group for v in self.engine.snapshot()],['wind'])

    def test_group_fade_is_visible_until_its_bus_transition_finishes(self):
        self.engine.dispatch(self.play(),0)
        self.engine.dispatch(AudioCommand('audio_volume','birds',gain=.25,fade_s=1,scope='group'),0)
        self.assertTrue(self.engine.snapshot()[0].fading)
        self.engine.tick(1.1)
        self.assertFalse(self.engine.snapshot()[0].fading)
        self.assertAlmostEqual(self.engine.snapshot()[0].gain,.25)

    def test_same_owner_loop_does_not_restart_and_reappearance_cancels_fade_out(self):
        self.engine.dispatch(self.play(),0)
        slot=self.engine.snapshot()[0].slot;clip=self.backend.active[slot]
        self.engine.dispatch(self.play(gain=.6,fade_s=.2),.2)
        self.assertIs(self.backend.active[slot],clip)
        self.engine.dispatch(AudioCommand('stop_sound','birds','camera:0',0,fade_s=1),.3)
        self.engine.dispatch(self.play(gain=.8,fade_s=.1),.4);self.engine.tick(1.5)
        self.assertEqual(len(self.engine.snapshot()),1)
        self.assertAlmostEqual(self.engine.snapshot()[0].gain,.8)

    def test_missing_or_invalid_replacement_keeps_playing_voice(self):
        self.engine.dispatch(self.play(),0);before=self.engine.snapshot()
        with self.assertRaises(OSError):self.engine.dispatch(AudioCommand('play_sound','birds','camera:0',0,'missing.wav'),.1)
        self.assertEqual(self.engine.snapshot(),before)
        bad=Path(self.temp.name)/'bad.wav';bad.write_text('not a wave')
        with self.assertRaises((wave.Error,EOFError)):self.engine.dispatch(AudioCommand('play_sound','birds','camera:0',0,str(bad)),.1)
        self.assertEqual(self.engine.snapshot(),before)

    def test_saturation_never_steals_an_existing_channel(self):
        for i in range(16):self.engine.dispatch(self.play(i),0)
        before=self.engine.snapshot()
        with self.assertRaises(ValueError):self.engine.dispatch(self.play(0,'extra'),.1)
        self.assertEqual(self.engine.snapshot(),before)

    def test_cache_limits_count_and_bytes_and_never_evicts_active_clip(self):
        self.engine.dispatch(self.play(),0);key=self.backend.active[0].key
        with patch('local_audio.MAX_CACHE_ITEMS',3):
            for i in range(6):self.backend.load(wav(Path(self.temp.name)/f'{i}.wav'))
        self.assertEqual(len(self.backend.cache),3)
        self.assertIn(key,self.backend.cache)
        with patch('local_audio.MAX_CACHE_BYTES',1):
            with self.assertRaises(ValueError):self.backend.load(wav(Path(self.temp.name)/'too-much.wav'))

    def test_file_limits_checked_before_decode_and_nonfinite_commands_rejected(self):
        long=wav(Path(self.temp.name)/'long.wav',seconds=31,rate=8000)
        with self.assertRaises(ValueError):inspect_clip(long)
        invalid=wav(Path(self.temp.name)/'three.wav',channels=3)
        with self.assertRaises(ValueError):inspect_clip(invalid)
        for kwargs in ({'gain':float('nan')},{'fade_s':float('inf')},{'gain':1.1},{'loop':'yes'},{'scope':'all'},{'marker_id':True}):
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):AudioCommand('play_sound','birds',**kwargs)

    def test_loading_time_does_not_consume_playback_fade_and_cancel_prevents_start(self):
        self.engine.dispatch(self.play(fade_s=1),0,clock=lambda:5)
        self.assertEqual(self.engine.snapshot()[0].gain,0)
        self.engine.tick(5.5);self.assertAlmostEqual(self.engine.snapshot()[0].gain,.5)
        self.engine.stop_all()
        self.assertFalse(self.engine.dispatch(self.play(),6,cancelled=lambda:True))
        self.assertFalse(self.engine.snapshot())

    def test_invalid_clock_does_not_change_active_voice(self):
        self.engine.dispatch(self.play(),1);before=self.engine.snapshot()
        for now in (0,float('nan'),float('inf'),True):
            with self.assertRaises(ValueError):self.engine.dispatch(self.play(),now)
            self.assertEqual(self.engine.snapshot(),before)
        with self.assertRaises(ValueError):self.engine.dispatch(self.play(),1,clock=lambda:float('nan'))
        self.assertEqual(self.engine.snapshot(),before)


class AudioControllerTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=wav(Path(self.temp.name)/'clip.wav')
        self.controller=AudioController(SilentAudioBackend);self.addCleanup(self.controller.close)

    def command(self):return AudioCommand('play_sound','test','camera:0',0,str(self.path),loop=True)

    def enable(self):
        self.controller.enable()
        self.assertTrue(wait_until(lambda:self.controller.snapshot().state=='ready'))

    def test_no_thread_device_or_deferred_playback_before_explicit_enable(self):
        self.assertIsNone(self.controller.thread)
        self.assertFalse(self.controller.submit(self.command()))
        self.enable();self.assertFalse(self.controller.snapshot().voices)
        self.assertTrue(self.controller.submit(self.command()))
        self.assertTrue(wait_until(lambda:len(self.controller.snapshot().voices)==1))

    def test_worker_updates_fades_without_tk_and_can_stop_disable_and_reenable(self):
        self.enable();self.controller.submit(self.command())
        self.assertTrue(wait_until(lambda:len(self.controller.snapshot().voices)==1))
        self.controller.set_master(.2)
        self.assertTrue(wait_until(lambda:abs(self.controller.snapshot().voices[0].gain-.2)<.01))
        self.controller.stop_all();self.assertTrue(wait_until(lambda:not self.controller.snapshot().voices))
        self.controller.disable();self.assertTrue(wait_until(lambda:self.controller.snapshot().state=='disabled'))
        self.enable();self.assertFalse(self.controller.snapshot().voices)

    def test_initialization_failure_is_reported_and_can_be_retried_explicitly(self):
        def fail():raise RuntimeError('device not found')
        self.controller.factory=fail;self.controller.enable()
        self.assertTrue(wait_until(lambda:self.controller.snapshot().state=='error'))
        self.assertIn('device not found',self.controller.snapshot().detail)
        self.assertFalse(self.controller.submit(self.command()))
        self.controller.factory=SilentAudioBackend;self.enable()
        self.assertFalse(self.controller.snapshot().voices)

    def test_device_failure_closes_voices_and_does_not_replay_after_reenable(self):
        self.enable();self.controller.submit(self.command())
        self.assertTrue(wait_until(lambda:len(self.controller.snapshot().voices)==1))
        self.controller.engine.backend.closed=True
        self.assertTrue(wait_until(lambda:self.controller.snapshot().state=='error'))
        self.assertFalse(self.controller.snapshot().voices)
        self.enable();self.assertFalse(self.controller.snapshot().voices)

    def test_queue_bounded_and_stop_cancels_inflight_load_and_queued_plays(self):
        started=threading.Event();release=threading.Event()
        class Blocking(SilentAudioBackend):
            def load(self,path):
                started.set();release.wait(2);return super().load(path)
        self.controller.factory=Blocking;self.enable();self.controller.submit(self.command())
        self.assertTrue(started.wait(1))
        try:
            for _ in range(128):self.controller.submit(self.command())
            with self.assertRaises(ValueError):self.controller.submit(self.command())
            self.controller.stop_all();release.set()
            self.assertTrue(wait_until(lambda:any('cancel·lada' in entry[2] for entry in self.controller.snapshot().log)))
            self.assertTrue(wait_until(lambda:self.controller.snapshot().queued==0))
            self.assertFalse(self.controller.snapshot().voices)
        finally:release.set()

    def test_close_before_activation_and_after_activation_is_idempotent(self):
        empty=AudioController(SilentAudioBackend)
        self.assertTrue(empty.close());self.assertFalse(empty.enable())
        self.enable();self.assertTrue(self.controller.close());self.assertTrue(self.controller.close())
        self.assertFalse(self.controller.enable())


@unittest.skipUnless(importlib.util.find_spec('pygame') and importlib.util.find_spec('soundfile'),'Optional pygame-ce and soundfile required')
class SDLBackendTests(unittest.TestCase):
    def setUp(self):
        self.driver=patch.dict(os.environ,{'SDL_AUDIODRIVER':'dummy'});self.driver.start();self.addCleanup(self.driver.stop)
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=wav(Path(self.temp.name)/'tone.wav',seconds=.12)
        self.backend=PygameAudioBackend();self.addCleanup(self.backend.close)

    def test_real_sdl_decode_resample_play_multiple_channels_volume_fade_and_stop(self):
        engine=AudioEngine(self.backend);now=time.monotonic()
        for i in range(5):engine.dispatch(AudioCommand('play_sound','layer','test:0',i,str(self.path),.7,.1,True),now)
        self.assertEqual(self.backend.pg.mixer.get_init(),(48000,-16,2))
        clip=next(iter(self.backend.cache.values()))
        self.assertEqual(len(clip.payload.get_raw()),clip.size_bytes)
        self.assertTrue(any(clip.payload.get_raw()))
        self.assertTrue(all(self.backend.pg.mixer.Channel(i).get_busy() for i in range(5)))
        engine.tick(now+.05)
        self.assertAlmostEqual(engine.snapshot()[0].gain,.35,places=2)
        engine.dispatch(AudioCommand('stop_sound','layer',scope='group'),now+.06)
        self.assertTrue(all(not self.backend.pg.mixer.Channel(i).get_busy() for i in range(5)))

    def test_real_sdl_ogg_decode_and_natural_completion(self):
        import numpy as np
        path=Path(self.temp.name)/'clip.ogg'
        self.backend.sf.write(str(path),np.zeros(4410,dtype=np.float32),44100,format='OGG',subtype='VORBIS')
        clip=self.backend.load(path);self.assertGreater(clip.duration_s,.09)
        self.backend.start(clip,0,False,time.monotonic())
        self.assertTrue(wait_until(lambda:not self.backend.busy(0,time.monotonic()),1))

    def test_existing_mixer_not_hijacked_and_disappearance_reported(self):
        with self.assertRaises(RuntimeError):PygameAudioBackend()
        self.assertEqual(self.backend.pg.mixer.get_init(),(48000,-16,2))
        self.backend.pg.mixer.quit()
        with self.assertRaises(RuntimeError):self.backend.check()

    def test_missing_optional_module_error_is_actionable(self):
        self.backend.close()
        with patch.dict('sys.modules',{'pygame':None}):
            with self.assertRaisesRegex(RuntimeError,'requirements-audio'):PygameAudioBackend()


if __name__=='__main__':unittest.main()
