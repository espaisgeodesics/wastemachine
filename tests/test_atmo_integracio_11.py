"""Headless regressions for ATMO editing and original-editor handoff."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from spatial_zones import SpatialMap, Zone
from spatial_zone_editor import ZoneEditor
from atmo_esfera_fx_integracio_11 import AtmoZoneEditor, SpatialPanel


class Value:
    def __init__(self, value=None): self.value=value
    def get(self): return self.value
    def set(self, value): self.value=value


class EditingTests(unittest.TestCase):
    def editor(self, config=None):
        editor=AtmoZoneEditor.__new__(AtmoZoneEditor)
        editor.config=config or SpatialMap()
        editor.current_id=None
        editor.cells=set()
        editor.visited=set()
        editor.geometry=(0,0,800)
        editor.loading=False
        editor.dirty=False
        editor.name=Value('Bosc')
        editor.enabled=Value(True)
        editor.image_path=Value('')
        editor.display_mode=Value('Mentre la targeta sigui a la zona')
        editor.duration_s=Value('3')
        editor.cards=[Value(i==4) for i in range(16)]
        editor.notice=Value()
        editor.window=None
        editor.draw=Mock()
        editor.on_change=Mock()
        editor.set_map=Mock()
        return editor

    def test_reuses_original_editing_and_image_methods(self):
        for name in ('press','drag','save_zone','select_zone','choose_image',
                     'remove_image','confirm_discard','set_map','update_thumbnail'):
            self.assertIs(getattr(AtmoZoneEditor,name),getattr(ZoneEditor,name))

    def test_drag_toggle_outside_circle_and_overlap(self):
        e=self.editor()
        e.press(SimpleNamespace(x=10,y=10))
        self.assertFalse(e.cells)
        a=SimpleNamespace(x=250,y=350)
        e.press(a);e.drag(a);e.drag(SimpleNamespace(x=250,y=450))
        self.assertEqual(e.cells,{(3,2),(4,2)})
        self.assertTrue(e.dirty)
        e.press(a)
        self.assertEqual(e.cells,{(4,2)})
        e.config=SpatialMap(zones=(Zone('a','Ocupada',{(3,2)},{4}),))
        e.press(a)
        self.assertNotIn((3,2),e.cells)

    def test_apply_preserves_id_cards_and_image_duration(self):
        e=self.editor()
        e.cells={(3,2),(4,2)}
        e.current_id='existing'
        e.config=SpatialMap(zones=(Zone('existing','Antiga',{(3,2)},{1}),))
        e.image_path.set('images/bosc.png')
        e.display_mode.set('Segons després de retirar-la')
        e.duration_s.set('2,5')
        self.assertTrue(e.save_zone())
        config=e.on_change.call_args.args[0]
        self.assertEqual(len(config.zones),1)
        z=config.zones[0]
        self.assertEqual((z.id,z.name),('existing','Bosc'))
        self.assertEqual(z.cells,frozenset({(3,2),(4,2)}))
        self.assertEqual(z.authorized_cards,frozenset({4}))
        self.assertEqual((z.image_path,z.display_mode,z.duration_s),('images/bosc.png','after_exit',2.5))
        self.assertEqual(SpatialMap.from_dict(config.to_dict()),config)

    def test_invalid_draft_never_reaches_engine(self):
        e=self.editor()
        for cells, seconds in ((set(),'3'),({(3,2)},'-1')):
            e.cells=cells;e.duration_s.set(seconds)
            with patch('spatial_zone_editor.messagebox.showerror'):
                self.assertFalse(e.save_zone())
            e.on_change.assert_not_called()

    def test_delete_can_be_cancelled(self):
        e=self.editor();e.current_id='a'
        e.config=SpatialMap(zones=(Zone('a','Bosc',{(3,2)},{4}),))
        with patch('atmo_esfera_fx_integracio_11.messagebox.askyesno',return_value=False):
            e.delete_zone()
        e.on_change.assert_not_called()
        with patch('atmo_esfera_fx_integracio_11.messagebox.askyesno',return_value=True):
            e.delete_zone()
        self.assertEqual(e.on_change.call_args.args[0].zones,())


class HandoffTests(unittest.TestCase):
    def panel(self):
        p=SpatialPanel.__new__(SpatialPanel)
        p.editor=Mock();p.editor.confirm_discard.return_value=True
        p.original_editor=None;p.original_mode=False
        p.app=SimpleNamespace(zone_editor=p.editor, spatial_map=SpatialMap(),
                              zone_window=None, update_spatial_editor_runtime=Mock())
        p.host=Mock();p.return_panel=Mock()
        p.workspace=SimpleNamespace(win=Mock())
        def original_open(default_card=None):
            if p.app.zone_window is None:
                p.app.zone_window=Mock()
                p.app.zone_editor=Mock()
                p.app.zone_editor.confirm_discard.return_value=True
        p.original_open=Mock(side_effect=original_open)
        return p

    def test_cancel_keeps_embedded_draft_and_does_not_open_window(self):
        p=self.panel();p.editor.confirm_discard.return_value=False
        self.assertIsNone(p.open_original())
        self.assertIs(p.app.zone_editor,p.editor)
        p.original_open.assert_not_called()
        p.editor.set_map.assert_not_called()

    def test_roundtrip_registers_exactly_one_editor_and_reloads_map(self):
        p=self.panel();p.open_original(4)
        original=p.original_editor
        self.assertTrue(p.original_mode)
        self.assertIs(p.app.zone_editor,original)
        updated=SpatialMap(zones=(Zone('a','Bosc',{(3,2)},{4}),))
        p.app.spatial_map=updated
        original.confirm_discard.return_value=False
        self.assertFalse(p.return_to_atmo())
        self.assertIs(p.app.zone_editor,original)
        original.confirm_discard.return_value=True
        self.assertTrue(p.return_to_atmo())
        self.assertIs(p.app.zone_editor,p.editor)
        p.editor.set_map.assert_called_with(updated)
        p.open_original()
        self.assertIs(p.app.zone_editor,original)
        original.set_map.assert_called_with(updated)

    def test_open_failure_restores_engine_editor(self):
        p=self.panel();p.original_open.side_effect=RuntimeError('failure')
        with self.assertRaises(RuntimeError):p.open_original()
        self.assertIs(p.app.zone_editor,p.editor)
        self.assertFalse(p.original_mode)


class BaselineTests(unittest.TestCase):
    def test_startup_screens_and_engine_startup_are_unchanged(self):
        root=Path(__file__).resolve().parent
        if not (root/'atmo_esfera_fx_integracio_10b.py').exists():root=root.parent
        def functions(path):
            return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(path.read_text(encoding='utf-8')).body if isinstance(n,ast.FunctionDef)}
        old=functions(root/'atmo_esfera_fx_integracio_10b.py')
        new=functions(root/'atmo_esfera_fx_integracio_11.py')
        for name in ('main','open_engine','label','btn'):
            self.assertEqual(old[name],new[name])


if __name__=='__main__':unittest.main()
