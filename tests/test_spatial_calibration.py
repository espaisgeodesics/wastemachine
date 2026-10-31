import os
import time
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch
import numpy as np
from spatial_calibration import CalibrationEditor
from spatial_zones import Calibration, SpatialMap, Zone
from test_camera import app_module as m


@unittest.skipUnless(os.environ.get('DISPLAY') or os.name=='nt','Requires a graphical display')
class CalibrationTests(unittest.TestCase):
    def setUp(self):
        self.root=m.tk.Tk();self.root.geometry('900x650')
        self.frame=np.full((480,640,3),(20,50,80),np.uint8)
        self.context=(0,1,0,(480,640));self.stamp=time.monotonic();self.saved=None;self.applied=Mock()
        self.editor=CalibrationEditor(self.root,lambda:(self.frame,self.stamp),lambda:self.context,lambda:self.saved,self.applied)
        self.root.update()

    def tearDown(self):self.root.destroy()

    def click(self,x,y):
        left,top,width,height=self.editor.bounds
        self.editor.click(SimpleNamespace(x=left+x*width,y=top+y*height))

    def mark(self):
        self.assertTrue(self.editor.freeze())
        for point in ((.5,0),(1,.5),(.5,1),(0,.5)):self.click(*point)

    def test_snapshot_is_immutable_and_letterbox_clicks_are_normalized(self):
        self.assertTrue(self.editor.freeze());self.frame[:]=0
        self.assertTrue(self.editor.frame.any())
        left,top,width,height=self.editor.bounds
        before=self.editor.points.copy()
        self.editor.click(SimpleNamespace(x=left-1,y=top+10));self.assertEqual(before,self.editor.points)
        self.click(.3,.45);self.assertAlmostEqual(self.editor.points[0][0],.3);self.assertAlmostEqual(self.editor.points[0][1],.45)
        self.root.geometry('1000x700');self.root.update()
        self.editor.selected.set(0);self.click(.4,.5)
        self.assertAlmostEqual(self.editor.points[0][0],.4)

    def test_apply_valid_calibration_and_reselect_point(self):
        self.mark();self.editor.selected.set(0);self.click(.5,.01)
        self.assertTrue(self.editor.apply());calibration=self.applied.call_args.args[0]
        self.assertIsInstance(calibration,Calibration)
        np.testing.assert_allclose(calibration.project((.5,.01)),(.5,0),atol=1e-8)

    def test_incomplete_crossed_and_collinear_points_do_not_apply(self):
        self.assertFalse(self.editor.apply());self.editor.freeze()
        for points in ([(.5,0),None,None,None],[(.1,.1),(.9,.9),(.9,.1),(.1,.9)],[(.1,.1),(.3,.3),(.5,.5),(.7,.7)]):
            self.editor.points=points;self.assertFalse(self.editor.apply())
        self.applied.assert_not_called()

    def test_stale_or_absent_camera_cannot_be_captured(self):
        self.stamp=time.monotonic()-2;self.assertFalse(self.editor.freeze())
        self.frame=None;self.assertFalse(self.editor.freeze())
        self.editor.refresh();self.assertIsNone(self.editor.bounds)

    def test_context_change_blocks_applying_to_other_project_or_camera(self):
        self.mark();self.context=(1,1,0,(480,640))
        self.assertFalse(self.editor.apply());self.applied.assert_not_called()
        self.assertIn('Repeteix',self.editor.notice.get())

    def test_restart_keeps_saved_calibration_until_a_valid_apply(self):
        self.saved=Calibration(((.5,0),(1,.5),(.5,1),(0,.5)))
        self.editor.freeze();self.assertEqual(tuple(self.editor.points),self.saved.camera_points)
        self.editor.restart();self.assertFalse(self.editor.frozen);self.assertEqual(self.editor.points,[None]*4)
        self.applied.assert_not_called()


@unittest.skipUnless(os.environ.get('DISPLAY') or os.name=='nt','Requires a graphical display')
class CalibrationIntegrationTests(unittest.TestCase):
    def test_apply_persists_with_zones_and_new_project_resets_capture(self):
        root=m.tk.Tk()
        with patch.object(m.mido,'get_output_names',return_value=[]):app=m.App(root)
        app.arp_stop.set();app.arp_thread.join(timeout=1)
        try:
            app.open_zone_editor();app.open_calibration_editor();root.update()
            config=SpatialMap(zones=(Zone('a','Bosc',{(3,2)},{4}),))
            app.apply_spatial_map(config);app.refresh_zone_editor();app.midi=Mock()
            app.camera_frame=np.zeros((480,640,3),np.uint8);app.camera_frame_stamp=time.monotonic()
            editor=app.calibration_editor;self.assertTrue(editor.freeze())
            editor.points=[(.5,0),(1,.5),(.5,1),(0,.5)]
            self.assertTrue(editor.apply());self.assertEqual(app.spatial_map.zones,config.zones)
            self.assertIn('Calibració matemàtica vàlida',app.zone_editor.calibration_info.get())
            with TemporaryDirectory() as folder:
                app.project=str(Path(folder)/'project.json');app.save_project()
                data=json.loads(Path(app.project).read_text())
                self.assertIsNotNone(SpatialMap.from_project(data).calibration)
                with patch.object(m.filedialog,'askopenfilename',return_value=app.project):app.open_project()
                self.assertIsNotNone(app.spatial_map.calibration)
            app.midi.send.assert_not_called()
            app.new_project();self.assertIsNone(app.spatial_map.calibration);self.assertFalse(editor.frozen)
        finally:
            for timer in root.tk.call('after','info'):root.after_cancel(timer)
            app.close()

if __name__=='__main__':unittest.main()
