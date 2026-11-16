"""Visible ATMO main window and owned, nonmodal tool windows."""
import functools
import tkinter as tk
from atmo_runtime import adapt_engine, theme_widgets

TOOLS = {'open_kaoss_settings': 'kaoss_window', 'open_basic_function_settings': 'basic_function_window', 'open_zone_editor': 'zone_window', 'open_calibration_editor': 'calibration_window',
         'open_local_audio': 'audio_window', 'open_rules': 'rules_window',
         'open_participants': 'participant_window', 'open_simulator': 'simulator_window',
         'open_projection': 'projection', 'open_midi_diagnostics': 'diagnostics_window',
         'open_audio_settings': 'audio_settings_window', 'open_mute_settings': 'mute_settings_window',
         'open_cc_settings': 'cc_settings_window', 'open_music_settings': 'music_settings_window'}


def show_owned(window, root):
    if window is None or not window.winfo_exists(): return
    window.transient(root)
    window.attributes('-alpha', 1.0)
    theme_widgets(window)
    window.deiconify()
    window.lift()
    window.focus_set()


def primary_engine(module, mode='Joc'):
    adapted = adapt_engine(module)

    class PrimaryApp(adapted):
        def __init__(self, root):
            self.atmo_starting = True
            self.atmo_experience_mode = mode
            super().__init__(root)
            self.hide_startup_tools()

        def hide_startup_tools(self):
            windows = list(self.panel_windows.values())
            windows.extend(getattr(self, attribute, None) for attribute in TOOLS.values())
            for window in windows:
                if window is not None and window.winfo_exists(): window.withdraw()

        def finish_startup(self):
            self.hide_startup_tools()
            self.atmo_starting = False
            self.root.deiconify()
            self.root.lift()
            self.root.focus_set()

        def make_panel_window(self, key, title, geometry):
            window = super().make_panel_window(key, title, geometry)
            window.transient(self.root)
            window.withdraw()
            return window

        def show_panel(self, key):
            window = self.panel_windows.get(key)
            if window is None or not window.winfo_exists():
                raise ValueError('Panell no disponible: ' + key)
            if self.atmo_starting:
                window.withdraw()
                return
            show_owned(window, self.root)

    def owned(method, attribute):
        @functools.wraps(method)
        def opened(self, *args, **kwargs):
            result = method(self, *args, **kwargs)
            window = getattr(self, attribute, None)
            if window is not None and window.winfo_exists():
                if self.atmo_starting: window.withdraw()
                else: show_owned(window, self.root)
            return result
        return opened
    for method, attribute in TOOLS.items():
        if hasattr(adapted, method):
            setattr(PrimaryApp, method, owned(getattr(adapted, method), attribute))
    return PrimaryApp
