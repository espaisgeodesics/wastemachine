import tempfile
import time
import unittest
from pathlib import Path
import numpy as np
from PIL import Image
from card_media import CardMediaPlayer, MediaDecoder, media_settings, rebase_card_media, fit_frame

class Decoder:
    def __init__(self):self.frame=None;self.key=None
    def request(self,key):self.key=key;self.frame=None
    def snapshot(self):return self.frame,'',0
    def close(self):pass

class FadeTests(unittest.TestCase):
    def setUp(self):
        self.now=0.;self.decoder=Decoder();self.player=CardMediaPlayer(self.decoder,lambda:self.now)
        self.base=np.full((18,32,3),20,np.uint8)
        self.settings=media_settings(dict(media_fade_in_s=2.,media_fade_out_s=2.))
    def start(self,value=220):
        self.player.request(('image.png',True,1),self.settings)
        self.decoder.frame=np.full((18,32,3),value,np.uint8)
        return self.player.apply(self.base)
    def test_entry_and_exit_interpolate_over_underlying_content(self):
        np.testing.assert_array_equal(self.start(),self.base)
        self.now=1;self.assertEqual(int(self.player.apply(self.base)[5,5,0]),120)
        self.now=2;self.assertEqual(int(self.player.apply(self.base)[5,5,0]),220)
        self.player.request(None);self.assertEqual(int(self.player.apply(self.base)[5,5,0]),220)
        self.now=3;self.assertEqual(int(self.player.apply(self.base)[5,5,0]),120)
        self.now=4;np.testing.assert_array_equal(self.player.apply(self.base),self.base)
        self.assertFalse(self.player.needs_update())
    def test_replacement_crossfades_and_does_not_modify_source(self):
        self.start(220);self.now=2;self.player.apply(self.base)
        original=self.base.copy();self.player.request(('next.png',True,2),self.settings)
        self.decoder.frame=np.zeros((18,32,3),np.uint8)
        self.assertEqual(int(self.player.apply(self.base)[5,5,0]),220)
        self.now=3;self.assertEqual(int(self.player.apply(self.base)[5,5,0]),110)
        self.now=4;self.assertFalse(self.player.apply(self.base).any())
        np.testing.assert_array_equal(self.base,original)
    def test_removal_during_entry_preserves_partial_opacity(self):
        self.start();self.now=.5;before=self.player.apply(self.base)
        self.player.request(None);np.testing.assert_array_equal(self.player.apply(self.base),before)
        self.now=1.5;self.assertEqual(int(self.player.apply(self.base)[5,5,0]),45)
    def test_zero_duration_is_an_explicit_immediate_transition(self):
        self.settings=media_settings(dict(media_fade_in_s=0,media_fade_out_s=0))
        self.assertEqual(int(self.start()[5,5,0]),220)
        self.player.request(None);np.testing.assert_array_equal(self.player.apply(self.base),self.base)
    def test_decode_delay_keeps_base_until_ready_and_then_starts_fade(self):
        self.player.request(('image.png',True,1),self.settings);self.now=10
        np.testing.assert_array_equal(self.player.apply(self.base),self.base)
        self.decoder.frame=np.full((18,32,3),220,np.uint8)
        np.testing.assert_array_equal(self.player.apply(self.base),self.base)
        self.now=11;self.assertEqual(int(self.player.apply(self.base)[5,5,0]),120)
    def test_small_images_expand_with_aspect_ratio_preserved(self):
        frame=np.full((10,10,3),200,np.uint8);out=fit_frame(frame,40,20)
        self.assertTrue((out[:,10:30]==200).all());self.assertFalse(out[:,:10].any())

class DecodeTests(unittest.TestCase):
    def wait_frame(self,decoder):
        limit=time.monotonic()+2
        while time.monotonic()<limit:
            frame,error,_=decoder.snapshot()
            if error:self.fail(error)
            if frame is not None:return frame
            time.sleep(.01)
        self.fail('Decoder did not provide frame')
    def test_real_image_decode_and_switch_uses_new_generation(self):
        with tempfile.TemporaryDirectory() as folder:
            a=Path(folder)/'a.png';b=Path(folder)/'b.png'
            Image.new('RGB',(32,18),(255,0,0)).save(a);Image.new('RGB',(32,18),(0,255,0)).save(b)
            decoder=MediaDecoder()
            try:
                decoder.request((str(a),True,1));self.assertEqual(self.wait_frame(decoder)[0,0].tolist(),[0,0,255])
                decoder.request((str(b),True,2));self.assertEqual(self.wait_frame(decoder)[0,0].tolist(),[0,255,0])
            finally:decoder.close()
            self.assertFalse(decoder.thread.is_alive())
    def test_video_loops_and_releases_decoder(self):
        class Capture:
            def __init__(self):self.position=0;self.rewinds=0;self.released=False
            def isOpened(self):return True
            def get(self,key):return 120
            def read(self):
                self.position+=1
                if self.position>2:return False,None
                return True,np.full((18,32,3),self.position*50,np.uint8)
            def set(self,key,value):self.position=0;self.rewinds+=1
            def release(self):self.released=True
        capture=Capture();decoder=MediaDecoder(lambda path:capture)
        try:
            decoder.request(('test.mp4',True,1));self.wait_frame(decoder)
            limit=time.monotonic()+2
            while capture.rewinds==0 and time.monotonic()<limit:time.sleep(.01)
            self.assertGreater(capture.rewinds,0)
            decoder.request(None)
        finally:decoder.close()
        self.assertTrue(capture.released)
        self.assertFalse(decoder.thread.is_alive())

    def test_fade_limits_and_save_as_rebase(self):
        for value in (-1,11,float('nan'),True):
            with self.assertRaises(ValueError):media_settings(dict(media_fade_in_s=value))
        original=[dict(media_path='media/test.png')]
        moved=rebase_card_media(original,'/tmp/old/project.json','/tmp/new/project.json')
        self.assertEqual(Path(moved[0]['media_path']).resolve(),Path('/tmp/old/media/test.png').resolve())
        self.assertEqual(original[0]['media_path'],'media/test.png')

if __name__=='__main__':unittest.main()
