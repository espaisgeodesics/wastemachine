import ast
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import numpy as np
from PIL import Image
from atmo_preview import map_frame,map_pointer,bounds
from spatial_zones import Calibration,SpatialMap,Grid,Zone,SpatialEngine,Stabilization
from spatial_zone_editor import _cell_polygon

CORNERS=((0,0),(1,0),(1,1),(0,1))
ENGINE=Path(__file__).resolve().parents[1]/'atmo_esfera_fx_4_5_15_pas_15_editor_musical_desplegable.py'

class FloorTests(unittest.TestCase):
    def test_real_floor_ratio_roundtrips_and_changes_runtime_domain(self):
        cal=Calibration(((.1,.15),(.8,.2),(.9,.8),(.2,.9)),CORNERS,'rectangle',2.)
        config=SpatialMap(calibration=cal,zones=(Zone('a','Corner',{(0,0)},{0}),))
        self.assertEqual(config.grid.cell_at((.01,.01)),(0,0))
        saved=SpatialMap.from_dict(json.loads(json.dumps(config.to_dict())))
        self.assertEqual(saved,config);self.assertEqual(saved.calibration.aspect_ratio,2.)
        np.testing.assert_allclose(cal.project(cal.camera_points[0]),(0,0),atol=1e-8)
        self.assertEqual(len(_cell_polygon(0,0,config.grid)),4)
    def test_old_calibration_defaults_remain_circle(self):
        points=((.5,0),(1,.5),(.5,1),(0,.5))
        cal=Calibration(points)
        self.assertEqual(cal.shape,'circle');self.assertEqual(cal.aspect_ratio,1)
        self.assertIsNone(Grid().cell_at((.01,.01)))
    def test_physical_ratio_is_used_for_map_and_inverse_click(self):
        cal=Calibration(CORNERS,CORNERS,'rectangle',3.)
        left,top,right,bottom=bounds(640,360,'rectangle',0,cal.aspect_ratio)
        self.assertAlmostEqual((right-left)/(bottom-top),3.)
        # Widget adds 4px border to each side, so frame pixels map directly.
        point=map_pointer(4+left+.25*(right-left),4+top+.75*(bottom-top),648,368,640,360,'circle',cal)
        np.testing.assert_allclose(point,(.25,.75),atol=.005)
    def test_media_content_is_letterboxed_without_stretching(self):
        cal=Calibration(CORNERS,CORNERS,'rectangle',2.)
        content=np.full((360,640,3),255,np.uint8)
        frame=map_frame(content,[],{}, {},SpatialMap(calibration=cal),'circle')
        left,top,right,bottom=bounds(640,360,'rectangle',0,2.)
        y=round((top+bottom)/2)
        self.assertFalse(frame[y,round(left+6)].any())
        self.assertTrue((frame[y,round((left+right)/2)]==255).all())
    def test_invalid_ratios_do_not_create_a_calibration(self):
        for ratio in (0,float('nan'),30):
            with self.assertRaises(ValueError):Calibration(CORNERS,CORNERS,'rectangle',ratio)

class NewProjectTests(unittest.TestCase):
    def method(self,name,scope):
        cls=next(n for n in ast.parse(ENGINE.read_text()).body if isinstance(n,ast.ClassDef) and n.name=='App')
        node=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name==name)
        exec(compile(ast.Module(body=[node],type_ignores=[]),str(ENGINE),'exec'),scope)
        return scope[name]
    def test_cancel_save_failure_and_success(self):
        box=Mock();app=SimpleNamespace(root=object(),save_project=Mock(return_value=True),atmo_starting=False)
        confirm=self.method('confirm_new_project',dict(messagebox=box))
        for answer,result,save_ok in [(None,False,True),(False,True,True),(True,False,False),(True,True,True)]:
            app.save_project.reset_mock();app.save_project.return_value=save_ok;box.askyesnocancel.return_value=answer
            self.assertEqual(confirm(app),result)
            self.assertEqual(app.save_project.called,answer is True)
    def test_cancel_aborts_before_any_project_mutation(self):
        app=Mock();app.confirm_new_project.return_value=False
        self.method('new_project',{})(app)
        app.confirm_rule_discard.assert_not_called();app.live_kaoss.stop.assert_not_called();app.card_media.reset.assert_not_called()
    def test_initial_entry_skips_discard_dialog(self):
        box=Mock();app=SimpleNamespace(atmo_starting=True)
        self.assertTrue(self.method('confirm_new_project',dict(messagebox=box))(app));box.askyesnocancel.assert_not_called()

if __name__=='__main__':unittest.main()
