import unittest
from unittest.mock import Mock
import numpy as np
from test_camera import app_module as m

class VisualTests(unittest.TestCase):
    def app(self):
        a=m.App.__new__(m.App);a.bpm=120;a.current_visual=0
        yy,xx=np.mgrid[0:m.H,0:m.W].astype(np.float32)
        u=(xx-m.W/2)/(m.H/2);v=(yy-m.H/2)/(m.H/2)
        a._visual_coords=(u,v,np.sqrt(u*u+v*v)+1e-4,np.arctan2(v,u))
        a.cards=[dict(m.DEFAULTS[i]) for i in range(16)];a.active={}
        return a

    def test_idle_and_removal_go_black(self):
        a=self.app()
        self.assertFalse(a.compose_live_visuals(1).any())
        a.active={2:(.3,.4,0)};a.cards[2]['visual']=3
        self.assertTrue(a.compose_live_visuals(1).any())
        a.active.clear()
        self.assertFalse(a.compose_live_visuals(1).any())

    def test_layers_mix_and_duplicate_visuals_are_not_rendered_twice(self):
        a=self.app();a.active={0:(.5,.5,0),1:(.7,.2,0),2:(.8,.3,0)}
        a.cards[0]['visual']=0;a.cards[1]['visual']=1;a.cards[2]['visual']=0
        first=np.zeros((360,640,3),np.uint8);first[:,:,0]=60
        second=np.zeros((360,640,3),np.uint8);second[:,:,1]=120
        a.render=Mock(side_effect=lambda t,visual:first if visual==0 else second)
        frame=a.compose_live_visuals(1)
        self.assertEqual(a.render.call_count,2)
        self.assertGreater(frame[0,0,0],0)
        self.assertGreater(frame[0,0,1],0)
        self.assertEqual(frame[0,0,2],0)
        a.active.pop(1)
        np.testing.assert_array_equal(a.compose_live_visuals(1),first)

    def test_all_twelve_visuals_animate_and_are_distinct(self):
        a=self.app();frames=[]
        for i in range(12):
            frame=a.render(1,visual=i)
            self.assertEqual(frame.shape,(360,640,3));self.assertEqual(frame.dtype,np.uint8)
            self.assertGreater(frame.std(),3)
            self.assertFalse(np.array_equal(frame,a.render(2,visual=i)))
            frames.append(frame)
        self.assertEqual(len({frame.tobytes() for frame in frames}),12)

    def test_no_action_card_has_no_projected_visual(self):
        a=self.app();a.active={0:(.5,.5,0)};a.cards[0]['function']='Cap acció'
        self.assertFalse(a.compose_live_visuals(1).any())

if __name__=='__main__':unittest.main()
