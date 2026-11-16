import ast
import ctypes
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from atmo_primary import primary_engine
from atmo_windows import colorref, dark_titlebar

ROOT=Path(__file__).resolve().parents[1]
ENGINE=ROOT/'atmo_esfera_fx_4_5_15_pas_15_editor_musical_desplegable.py'


class TitlebarTests(unittest.TestCase):
    def test_colorref_uses_windows_bgr_byte_order(self):
        self.assertEqual(colorref('#0b1224'),0x24120b)
        self.assertEqual(colorref('#f5f7ff'),0xfff7f5)

    def test_native_dark_caption_attributes_and_no_geometry_change(self):
        calls=[]
        def setter(handle, attribute, pointer, size):
            calls.append((attribute,ctypes.cast(pointer,ctypes.POINTER(ctypes.c_uint)).contents.value))
            return 0
        user=Mock();user.GetAncestor.return_value=123
        dwm=Mock();dwm.DwmSetWindowAttribute.side_effect=setter
        window=Mock();window.winfo_id.return_value=50
        with patch('atmo_windows.sys.platform','win32'),patch.object(ctypes,'windll',SimpleNamespace(user32=user,dwmapi=dwm),create=True):
            self.assertTrue(dark_titlebar(window))
        self.assertIn((20,1),calls)
        self.assertIn((35,colorref('#0b1224')),calls)
        self.assertIn((36,colorref('#f5f7ff')),calls)
        user.SetWindowPos.assert_called_once_with(123,None,0,0,0,0,0x0037)
        window.overrideredirect.assert_not_called()

    def test_windows10_fallback_does_not_require_windows11_caption_colors(self):
        user=Mock();user.GetAncestor.return_value=123
        dwm=Mock();dwm.DwmSetWindowAttribute.side_effect=lambda handle,attr,*args:0 if attr==19 else -1
        with patch('atmo_windows.sys.platform','win32'),patch.object(ctypes,'windll',SimpleNamespace(user32=user,dwmapi=dwm),create=True):
            self.assertTrue(dark_titlebar(Mock()))
        self.assertTrue(any(call.args[1]==19 for call in dwm.DwmSetWindowAttribute.call_args_list))

    def test_other_platform_does_not_touch_native_apis(self):
        with patch('atmo_windows.sys.platform','linux'):
            self.assertFalse(dark_titlebar(Mock()))


class ModeAndFrameTests(unittest.TestCase):
    def test_mode_is_available_before_engine_build(self):
        class Engine:
            def __init__(self,root):
                self.root=root;self.panel_windows={};self.mode_at_build=self.atmo_experience_mode
        for mode in ('Joc','Música','Exposició','Instal·lació immersiva'):
            app=primary_engine(SimpleNamespace(App=Engine),mode)(Mock())
            self.assertEqual(app.mode_at_build,mode)

    def test_actual_menu_guards_only_show_game_tools_in_game_mode(self):
        tree=ast.parse(ENGINE.read_text(encoding='utf-8'))
        guards={}
        for node in ast.walk(tree):
            if not isinstance(node,ast.If):continue
            for line in node.body:
                if not isinstance(line,ast.Expr) or not isinstance(line.value,ast.Call):continue
                call=line.value
                if not isinstance(call.func,ast.Attribute) or call.func.attr!='add_cascade':continue
                for keyword in call.keywords:
                    if keyword.arg=='label' and isinstance(keyword.value,ast.Constant) and keyword.value.value in ('Participants','Regles'):
                        guards[keyword.value.value]=compile(ast.Expression(node.test),'<menu>','eval')
        self.assertEqual(set(guards),{'Participants','Regles'})
        for mode in ('Joc','Música','Exposició','Instal·lació immersiva'):
            for condition in guards.values():
                self.assertEqual(eval(condition,{'self':SimpleNamespace(atmo_experience_mode=mode)}),mode=='Joc')

    def test_card_frame_has_no_copper_border_or_rivets(self):
        tree=ast.parse(ENGINE.read_text(encoding='utf-8'))
        app=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='App')
        method=next(n for n in app.body if isinstance(n,ast.FunctionDef) and n.name=='sidebar_panel')
        tk=SimpleNamespace(Frame=Mock(),Label=Mock())
        scope={'tk':tk};exec(compile(ast.Module(body=[method],type_ignores=[]),str(ENGINE),'exec'),scope)
        scope['sidebar_panel'](None,Mock(),'EDITOR DE TARGETES')
        outer=tk.Frame.call_args_list[0].kwargs
        self.assertEqual(outer['highlightthickness'],0)
        self.assertEqual(outer['bd'],0)
        self.assertEqual(outer['bg'],'#0b1224')
        self.assertEqual(tk.Label.call_count,1)
        self.assertEqual(tk.Label.call_args.kwargs['text'],'EDITOR DE TARGETES')


if __name__=='__main__':unittest.main()
