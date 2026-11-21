import tempfile
import unittest
from pathlib import Path
import numpy as np
from PIL import Image
from spatial_zones import SpatialMap,Zone,Stabilization,Calibration
from atmo_projection_mosaic import ProjectionMosaic,tile_boxes

FAST=Stabilization(0,0,1,0)
CORNERS=((0,0),(1,0),(1,1),(0,1))

class MosaicTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.addCleanup(self.folder.cleanup)
        self.root=Path(self.folder.name);self.player=ProjectionMosaic();self.addCleanup(self.player.reset)
    def config(self,count=4,mode='presence'):
        zones=[]
        for i,color in enumerate(('red','green','blue','yellow')[:count]):
            path=self.root/f'{i}.png';Image.new('RGB',(40,40),color).save(path)
            zones.append(Zone(str(i),str(i),{(3,3)},{0},image_path=str(path),allow_overlap=True,display_mode=mode,duration_s=.5))
        return SpatialMap(zones=tuple(zones),calibration=Calibration(CORNERS,CORNERS,'square'),stabilization=FAST)
    def update(self,config,observations,now):
        return self.player.update(config,None,observations,{},[],False,False,now,normalized=True)
    def test_four_overlapping_images_stay_visible_in_four_quadrants(self):
        config=self.config();self.update(config,{0:(.45,.45)},0)
        frame=self.player.frame((400,200))
        self.assertEqual(frame[50,100].tolist(),[0,0,255])
        self.assertEqual(frame[50,300].tolist(),[0,128,0])
        self.assertEqual(frame[150,100].tolist(),[255,0,0])
        self.assertEqual(frame[150,300].tolist(),[0,255,255])
        self.assertFalse(self.update(config,{0:(.45,.45)},.1))
        self.assertEqual(len(self.player.zone_active),4)
        # Square photos remain square within the wider quadrant.
        self.assertFalse(frame[50,10].any())
    def test_two_and_three_layouts_cover_screen_without_empty_tiles(self):
        for count in (2,3):
            boxes=tile_boxes(count,600,300)
            self.assertEqual(len(boxes),count)
            self.assertEqual(sum((r-l)*(b-t) for l,t,r,b in boxes),600*300)
            self.assertTrue(all(b-t==300 for l,t,r,b in boxes))
    def test_stationary_cards_in_separate_zones_do_not_replace_each_other(self):
        config=self.config(2)
        from dataclasses import replace
        zones=(replace(config.zones[0],cells={(2,2)},authorized_cards={0}),replace(config.zones[1],cells={(5,5)},authorized_cards={1}))
        config=replace(config,zones=zones)
        self.update(config,{0:(.3,.3),1:(.7,.7)},0)
        self.assertEqual(len(self.player.zone_active),2)
        self.update(config,{0:(.3,.3)},.1)
        self.assertEqual(self.player.zone_active,['0'])
    def test_after_exit_duration_and_presence_removal(self):
        config=self.config(2,mode='after_exit');self.update(config,{0:(.45,.45)},0)
        self.update(config,{},.1);self.assertEqual(len(self.player.zone_active),2)
        self.update(config,{},.7);self.assertIsNone(self.player.frame((400,200)))
    def test_missing_photo_does_not_hide_other_valid_photo(self):
        config=self.config(2);(self.root/'1.png').unlink()
        self.update(config,{0:(.45,.45)},0)
        self.assertEqual(self.player.zone_active,['0']);self.assertTrue(self.player.error)
        self.assertIsNotNone(self.player.frame((400,200)))
    def test_two_card_images_use_independent_players_and_keep_fade_settings(self):
        import time
        cards=[]
        for i,color in enumerate(('red','blue')):
            path=self.root/f'card{i}.png';Image.new('RGB',(40,40),color).save(path)
            cards.append(dict(visual=14,function='Canviar visual',media_path=str(path),media_fade_in_s=0,media_fade_out_s=.5))
        self.player.update(SpatialMap(),None,{}, {0:(.2,.2,0),1:(.8,.8,0)},cards,False,False,0)
        deadline=time.monotonic()+2
        while time.monotonic()<deadline and any(p.decoder.snapshot()[0] is None for p in self.player.cards.values()):time.sleep(.01)
        frame=self.player.frame((400,200))
        self.assertEqual(frame[100,100].tolist(),[0,0,255]);self.assertEqual(frame[100,300].tolist(),[255,0,0])
        self.player.update(SpatialMap(),None,{}, {},cards,False,False,.1)
        self.assertTrue(all(p.tail is not None for p in self.player.cards.values()))

    def test_sources_and_cached_images_are_not_modified_by_mosaic(self):
        config=self.config(2);self.update(config,{0:(.45,.45)},0)
        loaded=self.player.zones['0'].image
        before=np.array(loaded.image).copy()
        self.player.frame((640,360));self.player.frame((1024,768))
        np.testing.assert_array_equal(np.array(loaded.image),before)

if __name__=='__main__':unittest.main()
