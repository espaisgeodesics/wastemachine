import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
import numpy as np
from unittest.mock import Mock, patch
from PIL import Image

from spatial_zones import SpatialMap, Zone, Calibration, check_image_asset
from spatial_zone_editor import rebase_map_images
from test_camera import app_module as m


class ImageReferenceTests(unittest.TestCase):
    def test_save_as_preserves_image_identity_across_directories(self):
        with TemporaryDirectory() as folder:
            root=Path(folder);old=root/'old'/'project.json';new=root/'new'/'project.json'
            image=root/'old'/'images'/'bosc.png';image.parent.mkdir(parents=True);image.touch()
            config=SpatialMap(zones=(Zone('bosc','Bosc',{(3,3)},{4},'images/bosc.png'),))
            rebased=rebase_map_images(config,old,new)
            self.assertEqual(check_image_asset(rebased.zones[0].image_path,new).path.resolve(),image.resolve())
            self.assertEqual(config.zones[0].image_path,'images/bosc.png')
            relative=rebase_map_images(rebased,new,old)
            self.assertEqual(relative.zones[0].image_path,'images/bosc.png')

    def test_unresolved_reference_rejected_without_assuming_working_directory(self):
        config=SpatialMap(zones=(Zone('bosc','Bosc',{(3,3)},{4},'bosc.jpg'),))
        with self.assertRaises(ValueError):rebase_map_images(config,None,'project.json')


@unittest.skipUnless(os.environ.get('DISPLAY') or os.name=='nt','Requires a graphical display')
class ZoneEditorTests(unittest.TestCase):
    def setUp(self):
        self.root=m.tk.Tk()
        with patch.object(m.mido,'get_output_names',return_value=[]):self.app=m.App(self.root)
        self.app.arp_stop.set();self.app.arp_thread.join(timeout=1)
        self.app.open_zone_editor();self.root.update()
        self.editor=self.app.zone_editor
        self.app.midi=Mock()

    def tearDown(self):
        self.editor.dirty=False
        for timer in self.root.tk.call('after','info'):self.root.after_cancel(timer)
        self.app.close()

    def event(self,row,column):
        ox,oy,size=self.editor.geometry
        return SimpleNamespace(x=ox+(column+.5)/8*size,y=oy+(row+.5)/8*size)

    def create_zone(self,name='Bosc',cells=((3,2),(4,2)),card=4):
        self.editor.name.set(name);self.editor.cards[card].set(True)
        for row,column in cells:self.editor.press(self.event(row,column))
        self.assertTrue(self.editor.save_zone())
        return self.editor.current_id

    def test_grouped_selection_authorization_modification_and_delete(self):
        id=self.create_zone()
        zone=self.app.spatial_map.zones[0]
        self.assertEqual(zone.cells,frozenset({(3,2),(4,2)}))
        self.assertEqual(zone.authorized_cards,frozenset({4}))
        self.editor.name.set('Bosc nocturn');self.editor.cards[5].set(True)
        self.assertTrue(self.editor.save_zone())
        self.assertEqual(self.app.spatial_map.zones[0].id,id)
        self.assertEqual(self.app.spatial_map.zones[0].name,'Bosc nocturn')
        self.editor.delete_zone()
        self.assertFalse(self.app.spatial_map.zones)
        self.app.midi.send.assert_not_called()

    def test_outside_click_overlap_and_drag_do_not_corrupt_map(self):
        self.editor.press(self.event(0,0));self.assertFalse(self.editor.cells)
        self.editor.press(self.event(3,2));self.editor.drag(self.event(3,2));self.editor.drag(self.event(4,2))
        self.assertEqual(self.editor.cells,{(3,2),(4,2)})
        self.editor.name.set('Primera');self.assertTrue(self.editor.save_zone())
        first=self.app.spatial_map
        self.editor.new_zone();self.editor.press(self.event(3,2))
        self.assertFalse(self.editor.cells)
        self.editor.cells={(3,2)};self.editor.name.set('Solapada')
        with patch.object(m.messagebox,'showerror') as error:
            self.assertFalse(self.editor.save_zone());error.assert_called_once()
        self.assertEqual(self.app.spatial_map,first)

    def test_preview_loading_missing_corrupt_and_no_reload_on_grid_changes(self):
        with TemporaryDirectory() as folder:
            image=Path(folder)/'bosc.png';Image.new('RGB',(500,200),'green').save(image)
            with patch.object(m.filedialog,'askopenfilename',return_value=str(image)):self.editor.choose_image()
            self.assertIsNotNone(self.editor.thumbnail)
            with patch('spatial_zone_editor.Image.open') as opened:
                self.editor.press(self.event(3,2));self.editor.draw();opened.assert_not_called()
            image.unlink();self.editor.update_thumbnail()
            self.assertIn('Falta',self.editor.image_preview.cget('text'))
            image.write_bytes(b'broken');self.editor.update_thumbnail()
            self.assertIn('no vàlida',self.editor.image_preview.cget('text'))
            self.editor.remove_image()
            self.assertIn('Sense imatge',self.editor.image_preview.cget('text'))
            self.assertEqual(int(self.editor.image_preview.cget('width')),32)

    def test_project_roundtrip_relative_assets_and_legacy_project(self):
        with TemporaryDirectory() as folder:
            root=Path(folder);image=root/'bosc.png';Image.new('RGB',(50,50),'green').save(image)
            self.editor.image_path.set(str(image));self.create_zone()
            self.app.project=str(root/'project.json');self.app.save_project()
            data=json.loads(Path(self.app.project).read_text(encoding='utf-8'))
            self.assertEqual(data['spatial_zones']['zones'][0]['image_path'],'bosc.png')
            self.app.spatial_map=SpatialMap()
            with patch.object(m.filedialog,'askopenfilename',return_value=self.app.project):self.app.open_project()
            self.assertEqual(self.app.spatial_map.zones[0].name,'Bosc')
            self.assertIsNotNone(self.editor.thumbnail)
            data.pop('spatial_zones');Path(self.app.project).write_text(json.dumps(data),encoding='utf-8')
            with patch.object(m.filedialog,'askopenfilename',return_value=self.app.project):self.app.open_project()
            self.assertFalse(self.app.spatial_map.zones)
            self.assertIn('SENSE CALIBRACIÓ',self.editor.calibration_info.get())

    def test_calibrated_projection_latches_photo_and_preview_keeps_guides(self):
        with TemporaryDirectory() as folder:
            image=Path(folder)/'scene.png';Image.new('RGB',(100,50),'red').save(image)
            self.app.spatial_map=SpatialMap(zones=(Zone('scene','Bosc',{(3,2)},{4},str(image)),),
                calibration=Calibration(((.5,0),(1,.5),(.5,1),(0,.5))))
            self.app.reset_spatial_projection()
            self.app.cards[4]['function']=m.ZONE_FUNCTION
            for now in (0,.08,.16):
                self.app.activate(4,.3,.45,0)
                self.app.process_spatial_frame({4:(.3,.45)}, {},now)
            self.app.last_frame=self.app.compose_output_frame(1)
            self.app.proj_label=Mock()
            self.app.proj_label.winfo_width.return_value=400
            self.app.proj_label.winfo_height.return_value=300
            output=self.app.projector_frame()
            self.assertEqual(output.shape,(300,400,3))
            np.testing.assert_array_equal(output[150,200],[0,0,255])
            np.testing.assert_array_equal(output[0,200],[0,0,0])
            self.assertFalse(np.array_equal(self.app.live_preview_frame(),self.app.last_frame))
            self.app.deactivate(4)
            self.app.process_spatial_frame({}, {},.24);self.app.process_spatial_frame({}, {},.45)
            np.testing.assert_array_equal(self.app.projector_frame(),output)
            self.assertIn('Bosc',self.editor.runtime_info.get())
            self.app.midi.send.assert_not_called()
            self.app.release_zone_scene()
            self.assertEqual(self.app.zone_projection.mode,'live')

    def test_presence_expiry_reaches_real_projector_as_black(self):
        with TemporaryDirectory() as folder:
            image=Path(folder)/'photo.png';Image.new('RGB',(50,50),'red').save(image)
            self.app.spatial_map=SpatialMap(zones=(Zone('a','Bosc',{(3,2)},{4},str(image),display_mode='presence'),),
                calibration=Calibration(((.5,0),(1,.5),(.5,1),(0,.5))))
            self.app.reset_spatial_projection()
            for now in (0,.08,.16):self.app.process_spatial_frame({4:(.3,.45)}, {},now)
            self.assertTrue(self.app.compose_output_frame(1).any())
            self.app.process_spatial_frame({}, {},.24);self.app.process_spatial_frame({}, {},.45)
            self.app.last_frame=self.app.compose_output_frame(2)
            self.app.proj_label=Mock();self.app.proj_label.winfo_width.return_value=400;self.app.proj_label.winfo_height.return_value=300
            self.assertFalse(self.app.last_frame.any());self.assertFalse(self.app.projector_frame().any())
            self.assertIn('negre en repòs',self.editor.runtime_info.get())
            self.app.midi.send.assert_not_called()

    def test_image_duration_editor_defaults_validation_and_reload(self):
        self.assertEqual(self.editor.display_mode.get(),'Mentre la targeta sigui a la zona')
        self.assertEqual(str(self.editor.duration_entry.cget('state')),'disabled')
        self.editor.display_mode.set('Segons després de retirar-la');self.editor.update_duration_state()
        self.assertEqual(str(self.editor.duration_entry.cget('state')),'normal')
        self.editor.duration_s.set('2,5');self.create_zone()
        zone=self.app.spatial_map.zones[0]
        self.assertEqual(zone.display_mode,'after_exit');self.assertEqual(zone.duration_s,2.5)
        self.editor.duration_s.set('-3')
        with patch.object(m.messagebox,'showerror') as error:
            self.assertFalse(self.editor.save_zone());error.assert_called_once()
        self.assertEqual(self.app.spatial_map.zones[0],zone)
        self.editor._load_zone(zone.id);self.assertEqual(self.editor.duration_s.get(),'2.5')

    def test_pending_edits_are_not_silently_saved_or_discarded(self):
        with TemporaryDirectory() as folder:
            self.app.project=str(Path(folder)/'project.json')
            self.editor.name.set('Sense aplicar')
            with patch.object(m.messagebox,'showwarning') as warning:
                self.app.save_project();warning.assert_called_once()
            self.assertFalse(Path(self.app.project).exists())
            with patch.object(m.messagebox,'askyesno',return_value=False):
                self.editor.new_zone();self.app.new_project()
            self.assertEqual(self.editor.name.get(),'Sense aplicar')
            with patch.object(m.messagebox,'askyesno',return_value=True):self.editor.new_zone()
            self.assertFalse(self.editor.dirty)

    def test_card_function_opens_editor_and_does_not_generate_visual_or_midi(self):
        self.app.card_id.set('05');self.app.load_card();self.app.fun.set(m.ZONE_FUNCTION)
        self.app.on_function_selected()
        self.assertTrue(self.editor.cards[4].get())
        self.assertTrue(self.app.apply_card())
        self.app.activate(4,.3,.45,0)
        self.assertFalse(self.app.compose_live_visuals(1).any())
        self.app.midi.send.assert_not_called()
        self.assertEqual(self.app.cards[4]['function'],m.ZONE_FUNCTION)
        self.assertIn('SENSE CALIBRACIÓ',self.editor.calibration_info.get())


if __name__=='__main__':unittest.main()
