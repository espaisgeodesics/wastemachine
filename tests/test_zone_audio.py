from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from PIL import Image
from local_audio import AudioEngine, SilentAudioBackend
from spatial_zones import SpatialMap, SpatialEngine, Zone, Calibration, Stabilization
from spatial_projection import ZoneProjection
from spatial_zone_editor import rebase_map_images
from zone_audio import ZoneAudioPlayer
from test_local_audio import wav

FAST=Stabilization(0,0,1,0)
IDENTITY=Calibration(((.5,0),(1,.5),(.5,1),(0,.5)))


class Sink:
    def __init__(self, engine):
        self.engine=engine;self.now=0;self.ready=True;self.commands=[]
    def submit(self, command):
        if not self.ready:return False
        self.engine.dispatch(command,self.now)
        self.commands.append(command);return True
    def snapshot(self):return SimpleNamespace(state='ready' if self.ready else 'disabled',detail='Dispositiu desactivat',log=())


class ZoneAudioTests(unittest.TestCase):
    def setUp(self):
        folder=TemporaryDirectory();self.addCleanup(folder.cleanup);self.root=Path(folder.name)
        self.clip=wav(self.root/'clip.wav',seconds=2)
        self.image=self.root/'scene.png';Image.new('RGB',(20,20),'red').save(self.image)
        self.engine=AudioEngine(SilentAudioBackend());self.addCleanup(self.engine.close)
        self.sink=Sink(self.engine);self.audio=ZoneAudioPlayer(self.sink)

    def zone(self,id='a',**kwargs):
        return Zone(id,id,{(3,3)},{0,1},audio_path=str(self.clip),allow_overlap=True,**kwargs)

    def config(self,*zones,calibration=IDENTITY):
        return SpatialMap(zones=zones,calibration=calibration,stabilization=FAST)

    def update(self,points,now,normalized=True):
        self.sink.now=now;self.audio.update(points,now,normalized)

    def test_same_zone_starts_image_and_audio_on_the_same_observation(self):
        zone=self.zone(image_path=str(self.image))
        config=self.config(zone);projection=ZoneProjection(config)
        self.audio.configure(config)
        projection.process_normalized({0:(.45,.45)},{},0)
        self.update({0:(.45,.45)},0)
        self.assertEqual(projection.mode,'zone');self.assertEqual(projection.scene.zone_id,'a')
        self.assertEqual(len(self.engine.snapshot()),1)

    def test_overlapping_image_and_two_sounds_mix_independently(self):
        image=Zone('image','Imatge',{(3,3)},{0},image_path=str(self.image))
        config=self.config(image,self.zone('a'),self.zone('b'))
        self.audio.configure(config);self.update({0:(.45,.45)},0)
        scene=SpatialEngine(config).update_normalized({0:(.45,.45)},0).scene
        self.assertEqual(scene.zone_id,'image')
        self.assertEqual({voice.group for voice in self.engine.snapshot()},{'zone:a','zone:b'})

    def test_fade_in_and_exit_fade_out_reach_zero_and_release_voice(self):
        self.audio.configure(self.config(self.zone(audio_fade_in_s=.5,audio_fade_out_s=1)))
        self.update({0:(.45,.45)},0)
        self.engine.tick(.25);self.assertAlmostEqual(self.engine.snapshot()[0].gain,.4)
        self.update({},.3);self.engine.tick(.8)
        self.assertAlmostEqual(self.engine.snapshot()[0].gain,.24)
        self.engine.tick(1.3);self.assertFalse(self.engine.snapshot())

    def test_two_cards_share_one_zone_voice_until_last_leaves(self):
        self.audio.configure(self.config(self.zone(audio_fade_out_s=0)))
        self.update({0:(.45,.45),1:(.45,.45)},0)
        self.update({1:(.45,.45)},.1)
        self.assertEqual(len(self.engine.snapshot()),1)
        self.assertEqual(sum(c.kind=='play_sound' for c in self.sink.commands),1)
        self.update({},.2);self.assertFalse(self.engine.snapshot())

    def test_stationary_presence_does_not_retrigger_playback(self):
        self.audio.configure(self.config(self.zone()))
        for now in (0,.05,.1,.15):self.update({0:(.45,.45)},now)
        self.assertEqual(sum(c.kind=='play_sound' for c in self.sink.commands),1)

    def test_after_exit_delay_then_fade(self):
        self.audio.configure(self.config(self.zone(audio_mode='after_exit',audio_duration_s=.5,audio_fade_out_s=.2)))
        self.update({0:(.45,.45)},0);self.update({},.1);self.update({},.5)
        self.assertEqual(len(self.engine.snapshot()),1)
        self.update({},.7);self.engine.tick(.91);self.assertFalse(self.engine.snapshot())

    def test_once_ignores_loop_and_finishes_naturally(self):
        self.audio.configure(self.config(self.zone(audio_mode='once',audio_loop=True)))
        self.update({0:(.45,.45)},0);self.update({},.1)
        self.assertFalse(self.engine.snapshot()[0].loop)
        self.engine.tick(2.1);self.assertFalse(self.engine.snapshot())

    def test_exit_before_backend_enable_does_not_create_future_sound(self):
        self.sink.ready=False;self.audio.configure(self.config(self.zone()))
        self.update({0:(.45,.45)},0);self.update({},.1)
        self.sink.ready=True;self.update({},.2)
        self.assertFalse(self.engine.snapshot());self.assertFalse(self.sink.commands)

    def test_enabling_backend_while_occupied_starts_once(self):
        self.sink.ready=False;self.audio.configure(self.config(self.zone()))
        self.update({0:(.45,.45)},0);self.assertIn('Activa',self.audio.last_error)
        self.sink.ready=True;self.update({0:(.45,.45)},.1);self.update({0:(.45,.45)},.15)
        self.assertEqual(sum(c.kind=='play_sound' for c in self.sink.commands),1)

    def test_no_calibration_or_unauthorized_card_never_starts(self):
        self.audio.configure(self.config(self.zone(),calibration=None))
        self.update({0:(.45,.45)},0,False);self.assertFalse(self.sink.commands)
        self.audio.configure(self.config(self.zone()))
        self.update({2:(.45,.45)},.1);self.assertFalse(self.sink.commands)

    def test_disabled_sound_zone_is_ignored(self):
        self.audio.configure(self.config(self.zone(enabled=False)))
        self.update({0:(.45,.45)},0);self.assertFalse(self.sink.commands)

    def test_project_reset_stops_old_layers_and_new_map_does_not_restart(self):
        self.audio.configure(self.config(self.zone()));self.update({0:(.45,.45)},0)
        self.audio.configure(self.config());self.assertFalse(self.engine.snapshot())
        self.update({0:(.45,.45)},.1);self.assertFalse(self.engine.snapshot())

    def test_reentry_during_fade_cancels_pending_stop_without_duplicate_voice(self):
        self.audio.configure(self.config(self.zone()))
        self.update({0:(.45,.45)},0);self.update({},.1);self.update({0:(.45,.45)},.2)
        self.engine.tick(1.3);self.assertEqual(len(self.engine.snapshot()),1)

    def test_clip_decode_error_is_reported_without_losing_image(self):
        zone=replace(self.zone(image_path=str(self.image)),audio_path=str(self.root/'missing.wav'))
        self.audio.configure(self.config(zone));self.update({0:(.45,.45)},0)
        self.assertIn('Àudio de zones',self.audio.last_error)
        projection=ZoneProjection(self.config(zone));projection.process_normalized({0:(.45,.45)},{},0)
        self.assertEqual(projection.mode,'zone')



class EditorSoundTests(unittest.TestCase):
    def test_zone_editor_applies_image_sound_fades_and_overlap_together(self):
        from test_atmo_integracio_11 import EditingTests
        editor=EditingTests().editor()
        editor.cells={(3,2)};editor.image_path.set('scene.png');editor.audio_path.set('sound.wav')
        editor.audio_gain.set('0,6');editor.audio_fade_in_s.set('2');editor.audio_fade_out_s.set('3')
        editor.allow_overlap.set(True);editor.priority.set('20')
        self.assertTrue(editor.save_zone())
        zone=editor.on_change.call_args.args[0].zones[0]
        self.assertEqual((zone.image_path,zone.audio_path),('scene.png','sound.wav'))
        self.assertEqual((zone.audio_gain,zone.audio_fade_in_s,zone.audio_fade_out_s),(.6,2,3))
        self.assertTrue(zone.allow_overlap);self.assertEqual(zone.priority,20)

    def test_invalid_fade_does_not_modify_map(self):
        from test_atmo_integracio_11 import EditingTests
        from unittest.mock import patch
        editor=EditingTests().editor();editor.cells={(3,2)};editor.audio_fade_out_s.set('-1')
        with patch('spatial_zone_editor.messagebox.showerror'):
            self.assertFalse(editor.save_zone())
        editor.on_change.assert_not_called()

    def test_choosing_audio_explicitly_enables_overlap(self):
        from test_atmo_integracio_11 import EditingTests
        from unittest.mock import Mock, patch
        editor=EditingTests().editor();editor.get_project=Mock(return_value=None)
        with patch('spatial_zone_editor.filedialog.askopenfilename',return_value='/tmp/clip.wav'):
            editor.choose_audio()
        self.assertTrue(editor.allow_overlap.get());self.assertEqual(editor.audio_path.get(),'/tmp/clip.wav')


class MultimediaModelTests(unittest.TestCase):
    def zone(self,id,**kwargs):return Zone(id,id,{(3,3)},{0},**kwargs)

    def test_explicit_overlap_keeps_old_nonoverlap_validation(self):
        with self.assertRaises(ValueError):SpatialMap(zones=(self.zone('a'),self.zone('b')))
        SpatialMap(zones=(self.zone('a'),self.zone('b',allow_overlap=True)))

    def test_image_priority_and_authorization_are_deterministic(self):
        a=self.zone('a',image_path='a.png',priority=10)
        b=self.zone('b',image_path='b.png',priority=20,allow_overlap=True)
        for zones in ((a,b),(b,a)):
            scene=SpatialEngine(SpatialMap(zones=zones,stabilization=FAST)).update_normalized({0:(.45,.45)},0).scene
            self.assertEqual(scene.zone_id,'b')
        b=replace(b,authorized_cards=frozenset({1}))
        result=SpatialEngine(SpatialMap(zones=(a,b),stabilization=FAST)).update_normalized({0:(.45,.45)},0)
        self.assertEqual(result.scene.zone_id,'a')

    def test_legacy_schema_is_read_with_audio_defaults_and_new_schema_roundtrips(self):
        legacy={'schema_version':1,'zones':[dict(id='a',name='a',cells=[[3,3]],authorized_cards=[0])]}
        config=SpatialMap.from_dict(legacy);self.assertIsNone(config.zones[0].audio_path)
        zone=replace(config.zones[0],audio_path='sound.wav',audio_gain=.4,audio_fade_in_s=2,
                     audio_fade_out_s=3,audio_mode='after_exit',audio_duration_s=5,allow_overlap=True,priority=30)
        result=SpatialMap(zones=(zone,));self.assertEqual(SpatialMap.from_dict(result.to_dict()),result)
        self.assertEqual(result.to_dict()['schema_version'],2)

    def test_audio_validation_rejects_invalid_parameters(self):
        for kwargs in (dict(audio_path='sound.mp3'),dict(audio_gain=2),dict(audio_fade_in_s=-1),
                       dict(audio_fade_out_s=float('nan')),dict(audio_loop=1),dict(priority=True),dict(audio_mode='bad')):
            with self.assertRaises(ValueError):self.zone('a',**kwargs)

    def test_save_as_preserves_both_audio_and_image_identity(self):
        with TemporaryDirectory() as folder:
            old=Path(folder)/'old'/'project.json';new=Path(folder)/'new'/'project.json'
            config=SpatialMap(zones=(self.zone('a',image_path='scene.png',audio_path='sound.wav'),))
            moved=rebase_map_images(config,old,new)
            self.assertEqual(Path(moved.zones[0].audio_path),old.parent/'sound.wav')
            self.assertEqual(Path(moved.zones[0].image_path),old.parent/'scene.png')
            returned=rebase_map_images(moved,new,old)
            self.assertEqual(returned.zones[0].audio_path,'sound.wav')


if __name__=='__main__':unittest.main()
