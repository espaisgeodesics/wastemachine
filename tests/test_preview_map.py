import ast
import math
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
import numpy as np

from atmo_preview import (NO_VISUAL, SURFACES, visual_index, assigned_visuals, mix_frames,
                          map_frame, bounds, floor_point, map_pointer)
from spatial_zones import SpatialMap, Calibration
from card_media import MEDIA_VISUAL, fit_frame

ROOT=Path(__file__).resolve().parents[1]
ENGINE=ROOT/'atmo_esfera_fx_4_5_15_pas_15_editor_musical_desplegable.py'


def method(name):
    tree=ast.parse(ENGINE.read_text(encoding='utf-8'))
    app=next(node for node in tree.body if isinstance(node,ast.ClassDef) and node.name=='App')
    function=next(node for node in app.body if isinstance(node,ast.FunctionDef) and node.name==name)
    scope=dict(np=np,math=math,MEDIA_VISUAL=MEDIA_VISUAL,fit_frame=fit_frame,NO_VISUAL=NO_VISUAL,assigned_visuals=assigned_visuals,
               mix_frames=mix_frames,visual_index=visual_index,W=640,H=360,
               ZONE_FUNCTION='Activar zona espacial',MUTE_FUNCTION='Control d’àudio / Mute',CHAOS_FUNCTION='Chaos Oscillator (Kaoss XY)',
               mido=SimpleNamespace(Message=lambda kind,**values:SimpleNamespace(type=kind,**values)))
    exec(compile(ast.Module(body=[function],type_ignores=[]),str(ENGINE),'exec'),scope)
    return scope[name]


def card(visual=NO_VISUAL,function='Nota MIDI'):
    return dict(visual=visual,function=function,axis='Horitzontal',channel=1,note=60)


class AssignedVisualTests(unittest.TestCase):
    def test_existing_visual_indices_unchanged_and_none_supported(self):
        for index in range(13):self.assertEqual(visual_index(index),index)
        for value in (NO_VISUAL,None,-1):self.assertEqual(visual_index(value),NO_VISUAL)
        for value in (True,'Cap',15,-2):
            with self.assertRaises(ValueError):visual_index(value)

    def test_cap_cards_do_not_render_but_other_cards_still_do(self):
        cards=[card(),card(2),card(12),card(3,'Cap acció'),card(4,'Activar zona espacial')]
        self.assertEqual(assigned_visuals(cards,{i:() for i in range(5)},'Activar zona espacial'),[2,12])

    def test_new_project_defaults_have_no_automatic_chromatic_demo(self):
        tree=ast.parse(ENGINE.read_text(encoding='utf-8'))
        assignment=next(node for node in tree.body if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='DEFAULTS' for t in node.targets))
        loop=next(node for node in tree.body if isinstance(node,ast.For) and isinstance(node.target,ast.Name) and node.target.id=='i')
        scope={'NO_VISUAL':NO_VISUAL}
        exec(compile(ast.Module(body=[assignment,loop],type_ignores=[]),str(ENGINE),'exec'),scope)
        self.assertEqual({c['visual'] for c in scope['DEFAULTS']},{NO_VISUAL})

    def test_native_midi_note_still_sends_with_cap_visual(self):
        app=Mock();app.muted=False;app.cards=[card()];app.active={};app.notes={}
        method('activate')(app,0,.5,.5,0)
        app.midi.send.assert_called_once()
        self.assertEqual(app.midi.send.call_args.args[0].type,'note_on')
        self.assertEqual(app.midi.send.call_args.args[0].note,60)

    def test_native_sound_action_still_triggers_with_cap_visual(self):
        app=Mock();app.muted=False;app.cards=[card(function='Àudio')];app.active={}
        method('activate')(app,0,.5,.5,0)
        app.trigger_audio.assert_called_once_with(0)

    def test_cap_visual_switch_does_not_clear_explicit_zone_image(self):
        app=Mock();app.muted=False;app.cards=[card(function='Canviar visual')];app.active={}
        method('activate')(app,0,.5,.5,0)
        app.zone_projection.request_live.assert_not_called();app.select_visual.assert_not_called()


class SeparationTests(unittest.TestCase):
    def app(self,cards):
        app=SimpleNamespace(cards=cards,active={i:(.5,.5,0) for i in range(len(cards))})
        app.projection_mosaic=SimpleNamespace(frame=lambda size:None)
        app.card_media=SimpleNamespace(key=None,tail=None,apply=lambda frame:frame)
        app.rule_outputs=Mock();app.rule_outputs.frame.return_value=None
        app.zone_projection=Mock();app.zone_projection.image_frame.return_value=None
        app.render=Mock(return_value=np.full((360,640,3),(0,90,20),np.uint8))
        app.color_by_position=Mock()
        app.projection_color_frame=Mock(return_value=np.full((360,640,3),(80,20,10),np.uint8))
        app.compose_live_visuals=lambda t,include_chromatic=True:method('compose_live_visuals')(app,t,include_chromatic)
        app.proj_label=Mock();app.proj_label.winfo_width.return_value=1280;app.proj_label.winfo_height.return_value=720
        return app

    def test_sound_only_projection_is_black_even_with_active_card(self):
        app=self.app([card(function='Àudio')])
        output=method('compose_output_frame')(app,1)
        self.assertFalse(output.any());app.render.assert_not_called()
        app.last_frame=output
        np.testing.assert_array_equal(method('projector_frame')(app),np.zeros((360,640,3),np.uint8))

    def test_no_active_card_does_not_project_demo(self):
        app=self.app([card(12)]);app.active={}
        self.assertFalse(method('compose_output_frame')(app,1).any())

    def test_preview_removes_chromatic_wash_but_keeps_other_figures(self):
        app=self.app([card(12),card(2)])
        output=method('compose_output_frame')(app,1)
        interior=method('preview_content_frame')(app,1)
        np.testing.assert_array_equal(interior,app.render.return_value)
        self.assertFalse(np.array_equal(output,interior))
        app.render.assert_called_once_with(1,visual=2)

    def test_mixed_projector_frame_is_not_flattened_to_chromatic_color(self):
        app=self.app([card(12),card(2)])
        app.last_frame=method('compose_output_frame')(app,1)
        self.assertIs(method('projector_frame')(app),app.last_frame)

    def test_explicit_zone_image_keeps_priority_and_is_not_modified(self):
        app=self.app([card()]);image=np.full((360,640,3),42,np.uint8)
        app.zone_projection.image_frame.return_value=image
        self.assertIs(method('compose_output_frame')(app,1),image)
        self.assertIs(method('preview_content_frame')(app,1),image)
        original=image.copy();map_frame(image,app.cards,app.active,{},SpatialMap())
        np.testing.assert_array_equal(image,original)


class MapTests(unittest.TestCase):
    def setUp(self):self.content=np.full((360,640,3),(7,8,9),np.uint8)

    def test_chromatic_color_is_on_outer_ring_not_inside(self):
        frame=map_frame(self.content,[],{}, {},SpatialMap(),color_bgr=(20,40,200))
        left,top,right,bottom=bounds(640,360,'circle')
        np.testing.assert_array_equal(frame[round(top)-6,320],(20,40,200))
        np.testing.assert_array_equal(frame[round((top+bottom)/2),320],(7,8,9))

    def test_shape_selects_circle_square_or_rectangle(self):
        for shape in SURFACES.values():
            left,top,right,bottom=bounds(640,360,shape)
            ratio=(right-left)/(bottom-top)
            self.assertAlmostEqual(ratio,640/360 if shape=='rectangle' else 1)
        circle=map_frame(self.content,[],{}, {},SpatialMap(),'circle')
        square=map_frame(self.content,[],{}, {},SpatialMap(),'square')
        left,top,right,bottom=bounds(640,360,'circle')
        point=(round(top+10),round(left+10))
        self.assertFalse(np.array_equal(circle[point],square[point]))

    def test_operator_marks_do_not_mutate_media_or_icons(self):
        content=self.content.copy();icon=np.full((360,640,3),100,np.uint8);original_icon=icon.copy()
        preview=map_frame(content,[card(2)],{0:(.5,.5,0)},{},SpatialMap(),icons={2:icon})
        np.testing.assert_array_equal(content,self.content)
        np.testing.assert_array_equal(icon,original_icon)
        self.assertFalse(np.array_equal(preview,content))


    def test_shared_music_grid_does_not_grow_brighter_with_more_cards(self):
        from PIL import Image, ImageDraw
        from atmo_preview import draw_music_layers
        canvas=Image.new('RGB',(640,360),'black')
        box=bounds(640,360,'circle',180)
        mask=Image.new('L',canvas.size);ImageDraw.Draw(mask).ellipse(box,fill=255)
        for layout in ('grid','radial'):
            first=dict(id=0,layout=layout,cell=None)
            second=dict(id=1,layout=layout,cell=None)
            one=draw_music_layers(canvas.copy(),box,mask,[first])
            two=draw_music_layers(canvas.copy(),box,mask,[first,second])
            np.testing.assert_array_equal(np.asarray(one),np.asarray(two))

    def test_radial_and_grid_maps_remain_visible_together(self):
        from PIL import Image, ImageDraw
        from atmo_preview import draw_music_layers
        canvas=Image.new('RGB',(640,360),'black')
        box=bounds(640,360,'circle',180)
        mask=Image.new('L',canvas.size);ImageDraw.Draw(mask).ellipse(box,fill=255)
        radial=dict(id=0,layout='radial',cell=(0,0),confirmed=True)
        grid=dict(id=1,layout='grid',cell=(5,2),confirmed=True)
        first=np.asarray(draw_music_layers(canvas.copy(),box,mask,[radial]))
        second=np.asarray(draw_music_layers(canvas.copy(),box,mask,[grid]))
        both=np.asarray(draw_music_layers(canvas.copy(),box,mask,[radial,grid]))
        self.assertGreater(np.count_nonzero(both),max(np.count_nonzero(first),np.count_nonzero(second)))
        self.assertFalse(np.any(both[np.asarray(mask)==0]))

    def test_calibrated_positions_are_projected_without_clamping(self):
        calibration=Calibration(((.5,.1),(.9,.5),(.5,.9),(.1,.5)))
        point=floor_point((.7,.5),calibration)
        self.assertAlmostEqual(point[0],.75)
        self.assertIsNone(floor_point((1.1,.5),None))

    def test_map_pointer_matches_rendered_geometry_and_inverse_calibration(self):
        calibration=Calibration(((.5,.1),(.9,.5),(.5,.9),(.1,.5)))
        left,top,right,bottom=bounds(640,360,'circle')
        point=map_pointer(left+.75*(right-left)+4,top+.5*(bottom-top)+4,648,368,640,360,'circle',calibration)
        self.assertAlmostEqual(point[0],.7);self.assertAlmostEqual(point[1],.5)
        self.assertIsNone(map_pointer(0,0,648,368,640,360,'circle'))


if __name__=='__main__':unittest.main()
