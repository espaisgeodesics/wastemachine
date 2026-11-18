import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import atmo_runtime as runtime


class Value:
    def __init__(self, value): self.value=value
    def get(self): return self.value
    def set(self, value): self.value=value


class Window:
    def __init__(self, state='withdrawn'):
        self.config={}
        self.current_state=state
        self.owner='hidden root'
        self.alpha=0
        self.caption='ATMO ESFERA FX · Eina'
        self.focus=False
    def winfo_exists(self): return True
    def transient(self, owner): self.owner=owner
    def attributes(self, key, value): self.alpha=value
    def deiconify(self): self.current_state='normal'
    def lift(self): pass
    def focus_set(self): self.focus=True
    def keys(self): return ['background']
    def winfo_class(self): return 'Toplevel'
    def cget(self, option): return '#151210'
    def configure(self, **kwargs): self.config=kwargs
    def title(self, text=None):
        if text is not None: self.caption=text
        return self.caption
    def winfo_children(self): return []


class MidiTests(unittest.TestCase):
    def app(self, ports=('loopMIDI Port',)):
        mido=Mock();mido.get_output_names.return_value=list(ports)
        class Original:
            def connect_midi(self):
                self.native_connect(self.midi_choice.get())
                if self.midi_choice.get() != 'Sense MIDI': self.midi=object()
        module=SimpleNamespace(App=Original,mido=mido,messagebox=Mock())
        klass=runtime.adapt_engine(module)
        app=klass.__new__(klass)
        app.midi_choice=Value('Sense MIDI');app.midi_cb={}
        app.status=Value('');app.midi_indicator=Mock();app.midi=None
        app.root=Mock();app.native_connect=Mock()
        return app,module

    def test_windows_uses_multimedia_backend_even_if_environment_backend_differs(self):
        m=Mock();m.get_output_names.return_value=['loopMIDI Port']
        ports,error,backend=runtime.detect_midi(m,'win32')
        self.assertEqual(ports,('loopMIDI Port',));self.assertIsNone(error)
        m.set_backend.assert_called_once_with('mido.backends.rtmidi/WINDOWS_MM')
        m.open_output.assert_not_called()

    def test_missing_mido_and_backend_errors_identify_python(self):
        ports,error,_=runtime.detect_midi(None,'win32')
        self.assertFalse(ports);self.assertIn(runtime.sys.executable,error)
        m=Mock();m.get_output_names.side_effect=ImportError('No module named rtmidi')
        ports,error,_=runtime.detect_midi(m,'win32')
        self.assertFalse(ports);self.assertIn('rtmidi',error)
        self.assertIn('WINDOWS_MM',error)

    def test_detecting_one_port_selects_but_does_not_connect(self):
        app,module=self.app();app.refresh_midi()
        self.assertEqual(app.midi_choice.get(),'loopMIDI Port')
        app.native_connect.assert_not_called();module.mido.open_output.assert_not_called()
        self.assertIn('prem Connectar',app.status.get())

    def test_multiple_ports_require_explicit_selection(self):
        app,_=self.app(('A','B'));app.refresh_midi()
        self.assertEqual(app.midi_choice.get(),'Sense MIDI')
        app.midi_choice.set('B');app.refresh_midi()
        self.assertEqual(app.midi_choice.get(),'B')

    def test_refresh_does_not_close_or_reconnect_live_output(self):
        app,_=self.app();port=app.midi=Mock()
        app.midi_choice.set('loopMIDI Port');app.refresh_midi()
        self.assertIs(app.midi,port);port.close.assert_not_called()
        app.native_connect.assert_not_called()

    def test_removed_port_is_not_silently_replaced_or_opened(self):
        app,module=self.app(('another port',))
        app.midi_choice.set('old port');self.assertFalse(app.connect_midi())
        app.native_connect.assert_not_called();module.messagebox.showerror.assert_called_once()

    def test_explicit_connect_and_disconnect_use_native_lifecycle(self):
        app,_=self.app();app.midi_choice.set('loopMIDI Port')
        self.assertTrue(app.connect_midi())
        app.native_connect.assert_called_once_with('loopMIDI Port')
        app.native_connect.reset_mock();app.midi_choice.set('Sense MIDI');app.connect_midi()
        app.native_connect.assert_called_once_with('Sense MIDI')

    def test_detection_error_stays_visible_without_startup_modal(self):
        app,module=self.app();module.mido.get_output_names.side_effect=RuntimeError('driver failed')
        app.refresh_midi()
        self.assertIn('driver failed',app.status.get())
        module.messagebox.showerror.assert_not_called()


class WindowTests(unittest.TestCase):
    def test_panel_is_independent_and_visible_with_atmo_title(self):
        w=Window();runtime.reveal_window(w)
        self.assertEqual(w.owner,'');self.assertEqual(w.alpha,1)
        self.assertEqual(w.current_state,'normal');self.assertTrue(w.focus)
        self.assertEqual(w.caption,'ATMO ESFERA FX · Eina')

    def test_panel_factory_detaches_before_first_show(self):
        window=Window()
        class Original:
            def make_panel_window(self,*args):return window
        app=runtime.adapt_engine(SimpleNamespace(App=Original))()
        self.assertIs(app.make_panel_window('midi','MIDI','400x300'),window)
        self.assertEqual(window.owner,'')
        app.panel_windows={'midi':window};app.show_panel('midi')
        self.assertEqual(window.current_state,'normal')
        with self.assertRaises(ValueError):app.show_panel('invalid')

    def test_existing_withdrawn_audio_window_reopens(self):
        class Original:
            def open_local_audio(self): self.audio_window.lift()
        app=runtime.adapt_engine(SimpleNamespace(App=Original))()
        app.audio_window=Window()
        app.open_local_audio()
        self.assertEqual(app.audio_window.current_state,'normal')

    def test_all_direct_transient_tool_methods_are_wrapped(self):
        methods=('open_music_settings','open_cc_settings','open_audio_settings',
                 'open_mute_settings','open_zone_editor','open_calibration_editor',
                 'open_rules','open_participants','open_simulator','open_local_audio',
                 'open_projection','open_midi_diagnostics')
        original=type('Original',(),{name:lambda self:None for name in methods})
        adapter=runtime.adapt_engine(SimpleNamespace(App=original))
        for name in methods:
            self.assertIsNot(getattr(adapter,name),getattr(original,name))

    def test_existing_atmo_accent_and_panel_colors_are_preserved(self):
        class Accent(Window):
            def keys(self):return ['background','foreground']
            def winfo_class(self):return 'Button'
            def cget(self, option):return runtime.CYAN if option=='background' else runtime.BG
        w=Accent();runtime.theme_widgets(w)
        self.assertNotIn('background',w.config)
        self.assertNotIn('foreground',w.config)

    def test_black_projection_background_is_preserved(self):
        class Black(Window):
            def cget(self, option):return 'black'
        w=Black();runtime.theme_widgets(w)
        self.assertNotIn('background',w.config)


class EntryPointTests(unittest.TestCase):
    def sources(self):
        root=Path(__file__).resolve().parent
        if not (root/'atmo_esfera_fx_integracio_12.py').exists():root=root.parent
        return root

    def test_initial_screens_unchanged(self):
        root=self.sources()
        def main(path):
            tree=ast.parse(path.read_text(encoding='utf-8'))
            return ast.dump(next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main'))
        self.assertEqual(main(root/'atmo_esfera_fx_integracio_11.py'),main(root/'atmo_esfera_fx_integracio_12.py'))

    def test_dashboard_calls_exist_in_engine(self):
        root=self.sources()
        engine=ast.parse((root/'atmo_esfera_fx_4_5_15_pas_15_editor_musical_desplegable.py').read_text(encoding='utf-8'))
        original=next(n for n in engine.body if isinstance(n,ast.ClassDef) and n.name=='App')
        methods={n.name for n in original.body if isinstance(n,ast.FunctionDef)}
        entry=ast.parse((root/'atmo_esfera_fx_integracio_12.py').read_text(encoding='utf-8'))
        names=set()
        for node in ast.walk(entry):
            if isinstance(node,ast.Call) and node.args and isinstance(node.args[0],ast.Constant):
                f=node.func
                if (isinstance(f,ast.Name) and f.id=='call') or (isinstance(f,ast.Attribute) and f.attr=='invoke'):
                    names.add(node.args[0].value)
        self.assertTrue(names)
        self.assertFalse(names-methods,names-methods)


if __name__=='__main__':unittest.main()
