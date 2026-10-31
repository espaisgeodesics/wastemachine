from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import numpy as np
from PIL import Image
from spatial_zones import SpatialMap, Zone, Calibration
from spatial_projection import ImageStore, ZoneProjection


class ProjectionTests(unittest.TestCase):
    def setUp(self):
        self.folder=TemporaryDirectory();self.addCleanup(self.folder.cleanup)
        self.root=Path(self.folder.name)
        for name,color in [('red','red'),('green','green')]:Image.new('RGB',(60,30),color).save(self.root/(name+'.png'))
        self.config=SpatialMap(zones=(Zone('a','Bosc',{(3,2)},{4},'red.png'),Zone('b','Desert',{(3,5)},{4},'green.png')))
        self.player=ZoneProjection(self.config,self.root/'project.json')

    def confirm(self,point,start=0,colors=None):
        for now in (start,start+.08,start+.16):self.player.process_normalized({4:point},colors or {},now)

    def test_image_latches_on_exit_and_loss_then_next_zone_replaces_it(self):
        self.confirm((.3,.45));image=self.player.image
        self.player.process_normalized({}, {},.24);self.player.process_normalized({}, {},.45)
        self.assertEqual(self.player.mode,'zone');self.assertIs(self.player.image,image)
        self.confirm((.7,.45),.53)
        self.assertEqual(self.player.zone_name,'Desert');self.assertNotEqual(self.player.image.token,image.token)

    def test_stationary_color_does_not_override_zone_but_new_movement_does(self):
        for now in (0,.08,.16):self.player.process_normalized({}, {0:(.5,.5)},now)
        self.assertEqual(self.player.mode,'color')
        self.confirm((.3,.45),.24,{0:(.5,.5)})
        self.assertEqual(self.player.mode,'zone')
        for now in (.48,.56,.64):self.player.process_normalized({4:(.3,.45)}, {0:(.8,.5)},now)
        self.assertEqual(self.player.mode,'color')
        self.player.process_normalized({}, {0:(.8,.5)},.72)
        self.player.process_normalized({}, {0:(.8,.5)},.95)
        self.confirm((.3,.45),1.03,{0:(.8,.5)})
        self.assertEqual(self.player.mode,'zone')

    def test_same_frame_zone_wins_over_color(self):
        self.confirm((.3,.45),colors={0:(.5,.5)})
        self.assertEqual(self.player.mode,'zone')

    def test_failed_image_preserves_last_successful_output(self):
        self.confirm((.3,.45));loaded=self.player.image
        (self.root/'green.png').write_bytes(b'broken')
        self.confirm((.7,.45),.24)
        self.assertIs(self.player.image,loaded);self.assertEqual(self.player.zone_name,'Bosc')
        self.assertIn('No s’ha carregat',self.player.last_error)

    def test_missing_image_preserves_output(self):
        self.confirm((.3,.45));(self.root/'green.png').unlink()
        self.confirm((.7,.45),.24)
        self.assertEqual(self.player.zone_name,'Bosc');self.assertTrue(self.player.last_error)

    def test_unauthorized_card_does_not_activate(self):
        for now in (0,.08,.16):self.player.process_normalized({5:(.3,.45)}, {},now)
        self.assertEqual(self.player.mode,'live')

    def test_camera_requires_calibration_but_color_still_works(self):
        for now in (0,.08,.16):self.player.process_camera({4:(.3,.45)}, {0:(.5,.5)},now)
        self.assertEqual(self.player.mode,'color');self.assertIsNone(self.player.image)
        self.assertIn('Sense calibració',self.player.last_error)

    def test_calibrated_camera_activates_image(self):
        config=SpatialMap(zones=self.config.zones,calibration=Calibration(((.5,0),(1,.5),(.5,1),(0,.5))))
        self.player.configure(config,self.root/'project.json',False)
        for now in (0,.08,.16):self.player.process_camera({4:(.3,.45)}, {},now)
        self.assertEqual(self.player.mode,'zone')

    def test_no_disk_reload_for_frames_or_reentry(self):
        with patch('spatial_projection.Image.open',wraps=Image.open) as opened:
            self.confirm((.3,.45))
            for now in (.24,.32,.4):
                self.player.process_normalized({4:(.3,.45)}, {},now)
                self.player.image_frame((640,360))
            self.player.process_normalized({}, {},.48);self.player.process_normalized({}, {},.71)
            self.confirm((.3,.45),.79)
            self.assertEqual(opened.call_count,1)

    def test_reset_and_explicit_release_do_not_resurrect_old_scene(self):
        self.confirm((.3,.45));self.player.request_live()
        self.assertIsNone(self.player.image_frame((640,360)))
        self.player.configure(SpatialMap(),None,False)
        self.assertIsNone(self.player.scene);self.assertIsNone(self.player.image)

    def test_output_preserves_aspect_ratio_and_is_readonly_bgr(self):
        self.confirm((.3,.45));frame=self.player.image_frame((100,100))
        self.assertEqual(frame.shape,(100,100,3));self.assertFalse(frame.flags.writeable)
        np.testing.assert_array_equal(frame[0,50],[0,0,0])
        np.testing.assert_array_equal(frame[50,50],[0,0,255])
        self.assertIs(frame,self.player.image_frame((100,100)))

    def test_transparency_is_composited_on_black(self):
        path=self.root/'alpha.png';Image.new('RGBA',(10,10),(255,0,0,128)).save(path)
        store=ImageStore();loaded=store.load(path,None)
        np.testing.assert_array_equal(store.fit(loaded,(10,10))[5,5],[0,0,128])

    def test_caches_are_bounded_and_relative_paths_need_project(self):
        store=ImageStore()
        with self.assertRaises(ValueError):store.load('red.png',None)
        for i in range(7):
            path=self.root/f'{i}.png';Image.new('RGB',(10,10),'red').save(path)
            loaded=store.load(path,None);store.fit(loaded,(10+i,10))
        self.assertEqual(len(store.images),4);self.assertEqual(len(store.frames),4)
        with self.assertRaises(ValueError):store.fit(loaded,(0,10))

if __name__=='__main__':unittest.main()
