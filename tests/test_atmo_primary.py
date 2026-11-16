import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from atmo_primary import primary_engine, show_owned
from test_atmo_runtime import Window


class Tool(Window):
    def withdraw(self): self.current_state='withdrawn'


class PrimaryTests(unittest.TestCase):
    def app(self):
        class Engine:
            def __init__(self, root):
                self.root=root;self.panel_windows={}
                self.visual_window=self.make_panel_window('visual','Visuals','400x300')
                self.show_panel('visual')
            def make_panel_window(self,key,title,geometry):
                tool=Tool();self.panel_windows[key]=tool;return tool
            def open_music_settings(self):
                if not hasattr(self,'music_settings_window'):self.music_settings_window=Tool()
            def new_project(self):self.show_panel('visual')
        klass=primary_engine(SimpleNamespace(App=Engine))
        return klass(Tool())

    def test_preview_remains_hidden_during_constructor_and_new_project(self):
        app=self.app()
        self.assertEqual(app.visual_window.current_state,'withdrawn')
        app.new_project();app.finish_startup()
        self.assertEqual(app.visual_window.current_state,'withdrawn')
        self.assertEqual(app.root.current_state,'normal')
        self.assertFalse(app.atmo_starting)

    def test_explicit_preview_request_is_owned_by_main_window(self):
        app=self.app();app.finish_startup();app.show_panel('visual')
        self.assertIs(app.visual_window.owner,app.root)
        self.assertEqual(app.visual_window.current_state,'normal')
        self.assertTrue(app.visual_window.focus)

    def test_direct_music_callback_is_owned_and_reopens(self):
        app=self.app();app.finish_startup();app.open_music_settings()
        self.assertIs(app.music_settings_window.owner,app.root)
        app.music_settings_window.withdraw();app.open_music_settings()
        self.assertEqual(app.music_settings_window.current_state,'normal')
        self.assertIs(app.music_settings_window.owner,app.root)

    def test_delayed_startup_layout_does_not_open_preview(self):
        app=self.app();app.finish_startup();app.raise_all_panels()
        self.assertEqual(app.visual_window.current_state,'withdrawn')

    def test_startup_direct_tool_request_is_hidden(self):
        app=self.app();app.open_music_settings()
        self.assertEqual(app.music_settings_window.current_state,'withdrawn')
        app.finish_startup()
        self.assertEqual(app.music_settings_window.current_state,'withdrawn')

    def test_hidden_or_missing_tool_is_safe(self):
        root=Tool();show_owned(None,root)
        missing=Mock();missing.winfo_exists.return_value=False
        show_owned(missing,root);missing.deiconify.assert_not_called()


class EntryTests(unittest.TestCase):
    def test_entry_has_no_dashboard_or_provisional_copy(self):
        root=Path(__file__).resolve().parents[1]
        path=root/'atmo_esfera_fx_integracio_15.py'
        source=path.read_text(encoding='utf-8')
        tree=ast.parse(source)
        self.assertNotIn('Workspace(',source)
        self.assertNotIn('en desenvolupament',source)
        self.assertNotIn('Tornar a ATMO',source)
        self.assertIn("root.after_idle(start_project)",source)
        self.assertIn("app.new_project()",source)
        self.assertIn("app.open_project()",source)
        self.assertIn('Instal·lació immersiva', (root/'atmo_esfera_fx_integracio_12.py').read_text(encoding='utf-8'))
        self.assertTrue(any(isinstance(n,ast.FunctionDef) and n.name=='main' for n in tree.body))

    def test_launchers_pin_validated_python(self):
        root=Path(__file__).resolve().parents[1]
        for name in ('OBRIR_ATMO.bat','OBRIR_ATMO_12.bat','OBRIR_ATMO_13.bat'):
            s=(root/name).read_text()
            self.assertIn('py -3.12 atmo_esfera_fx_integracio_15.py',s)
        self.assertIn('py -3.12', (root/'DIAGNOSI_MIDI_ATMO.bat').read_text())


if __name__=='__main__':unittest.main()
