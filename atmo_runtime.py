"""ATMO presentation and window/MIDI adapters; no project format changes."""
import functools
import sys
import tkinter as tk
from tkinter import ttk

BG = '#0b1224'
PANEL = '#16243d'
SURFACE = '#203452'
TEXT = '#f5f7ff'
MUTED = '#a8bad5'
CYAN = '#45d4d2'
PURPLE = '#9b8cff'


def title_atmo(text):
    text = text.replace('ATMO ESFERA FX', 'ATMO ESFERA FX').replace('ATMO ESFERA FX', 'ATMO ESFERA FX')
    return text if text.startswith('ATMO ESFERA FX') else 'ATMO ESFERA FX · ' + text


def configure_theme(root):
    style = ttk.Style(root)
    style.configure('.', background=BG, foreground=TEXT, font=('Segoe UI', 10))
    for name in ('TFrame', 'TLabel', 'TCheckbutton', 'TRadiobutton', 'TLabelFrame'):
        style.configure(name, background=BG, foreground=TEXT)
    style.configure('TLabelFrame', bordercolor=SURFACE, relief='flat')
    style.configure('TLabelFrame.Label', background=BG, foreground=CYAN, font=('Segoe UI', 10, 'bold'))
    for name in ('TButton', 'Accent.TButton'):
        style.configure(name, background=SURFACE if name == 'TButton' else CYAN,
                        foreground=TEXT if name == 'TButton' else BG, padding=(10, 7), borderwidth=0)
        style.map(name, background=[('pressed', PURPLE), ('active', PURPLE)],
                  foreground=[('disabled', MUTED), ('active', BG)])
    for name in ('TEntry', 'TCombobox', 'TSpinbox'):
        style.configure(name, fieldbackground=SURFACE, background=SURFACE, foreground=TEXT,
                        insertcolor=TEXT, arrowcolor=CYAN)
        style.map(name, fieldbackground=[('readonly', SURFACE), ('disabled', PANEL)],
                  foreground=[('readonly', TEXT), ('disabled', MUTED)])
    style.configure('Treeview', background=PANEL, fieldbackground=PANEL, foreground=TEXT, rowheight=25)
    style.configure('Treeview.Heading', background=SURFACE, foreground=CYAN, font=('Segoe UI', 10, 'bold'))
    style.map('Treeview', background=[('selected', CYAN)], foreground=[('selected', BG)])
    style.configure('TNotebook', background=BG, borderwidth=0)
    style.configure('TNotebook.Tab', background=SURFACE, foreground=TEXT, padding=(10, 6))
    style.map('TNotebook.Tab', background=[('selected', PANEL)], foreground=[('selected', CYAN)])
    style.configure('Vertical.TScrollbar', background=SURFACE, troughcolor=BG, arrowcolor=CYAN)
    style.configure('Horizontal.TScrollbar', background=SURFACE, troughcolor=BG, arrowcolor=CYAN)
    root.option_add('*TCombobox*Listbox.background', SURFACE)
    root.option_add('*TCombobox*Listbox.foreground', TEXT)
    root.option_add('*TCombobox*Listbox.selectBackground', CYAN)
    root.option_add('*TCombobox*Listbox.selectForeground', BG)


def theme_widgets(widget):
    """Style chrome only: keep images, projection black and semantic indicators."""
    try:
        options = set(widget.keys())
        kind = widget.winfo_class()
        if kind in ('Tk', 'Toplevel'):
            widget.title(title_atmo(widget.title()))
        if kind.startswith('T') and kind not in ('Tk', 'Toplevel') and 'foreground' in options:
            if str(widget.cget('foreground')) not in ('', BG, TEXT, MUTED, CYAN, PURPLE, 'red', 'green', '#7de0ac'):
                widget.configure(foreground=TEXT)
        if kind == 'Canvas' and str(widget.cget('background')).lower() in ('#171411', '#151210', '#261c16'):
            widget.configure(background=BG)
        classic = kind in ('Tk', 'Toplevel', 'Frame', 'Labelframe', 'Label', 'Button',
                           'Checkbutton', 'Radiobutton', 'Entry', 'Spinbox', 'Text', 'Scale', 'Menu')
        if classic:
            config = {}
            if 'background' in options and str(widget.cget('background')).lower() not in (BG, PANEL, SURFACE, CYAN, PURPLE, 'black', '#000000', '#a52626', '#406c39'):
                config['background'] = SURFACE if kind in ('Button', 'Entry', 'Text', 'Spinbox') else BG
            if 'foreground' in options:
                old = str(widget.cget('foreground')).lower()
                if old not in (BG, PANEL, SURFACE, TEXT, MUTED, CYAN, PURPLE, 'red', 'green', '#42c990', '#a52626'):
                    config['foreground'] = TEXT
            for key in ('insertbackground', 'activeforeground'):
                if key in options: config[key] = TEXT
            if 'activebackground' in options: config['activebackground'] = SURFACE
            if 'selectcolor' in options: config['selectcolor'] = SURFACE
            if 'readonlybackground' in options: config['readonlybackground'] = SURFACE
            if 'text' in options and 'ATMO ESFERA FX' in str(widget.cget('text')):
                config['text'] = str(widget.cget('text')).replace('ATMO ESFERA FX', 'ATMO ESFERA FX').replace('ATMO ESFERA FX', 'ATMO ESFERA FX')
            widget.configure(**config)
        for child in widget.winfo_children(): theme_widgets(child)
    except tk.TclError:
        return  # A tool may be destroyed by its own close callback.


def reveal_window(window):
    """Independent nonmodal window: hidden engine root must not hide the tool."""
    if window is None or not window.winfo_exists(): return
    window.transient('')
    window.attributes('-alpha', 1.0)
    theme_widgets(window)
    window.deiconify()
    window.lift()
    window.focus_set()


def detect_midi(mido_module, platform=None):
    """Use the Windows multimedia API for loopMIDI, independent of MIDO_BACKEND."""
    platform = sys.platform if platform is None else platform
    backend = 'mido.backends.rtmidi/WINDOWS_MM' if platform == 'win32' else 'mido.backends.rtmidi'
    if mido_module is None:
        return (), 'Falta el mòdul mido en aquest Python: ' + sys.executable, backend
    try:
        mido_module.set_backend(backend)
        return tuple(mido_module.get_output_names()), None, backend
    except Exception as exc:
        return (), f'{type(exc).__name__}: {exc}\nPython: {sys.executable}\nBackend: {backend}', backend


def adapt_engine(module):
    """Return an ATMO subclass. The source engine and standalone launcher stay intact."""
    original = module.App

    class AtmoApp(original):
        def build(self):
            super().build()
            configure_theme(self.root)
            self.midi_cb.unbind('<<ComboboxSelected>>')
            theme_widgets(self.root)
            self.root.title('ATMO ESFERA FX · Eines completes')

        def show_runtime_info(self):
            module.messagebox.showinfo('ATMO ESFERA FX · Versió i fitxer',
                'Integració ' + str(getattr(self, 'atmo_integration_version', 12)) + ' · Motor ' + module.APP_VERSION + '\nPython: ' + sys.executable,
                parent=getattr(self, 'atmo_dashboard', self.root))

        def resize_banner(self, event):
            canvas = self.banner_canvas
            canvas.configure(height=60, bg=BG)
            canvas.delete('all')
            canvas.create_text(18, 22, anchor='w', text='ATMO ESFERA FX',
                               fill=TEXT, font=('Segoe UI', 22, 'bold'))
            canvas.create_text(20, 48, anchor='w', text='L’espai es converteix en instrument',
                               fill=CYAN, font=('Segoe UI', 10))

        def raise_all_panels(self):
            pass  # Explicit tool requests only; no delayed layout exposing root.

        def make_panel_window(self, key, title, geometry):
            window = super().make_panel_window(key, title, geometry)
            window.transient('')
            window.title(title_atmo(title))
            return window

        def show_panel(self, key):
            window = self.panel_windows.get(key)
            if window is None or not window.winfo_exists():
                raise ValueError('Panell no disponible: ' + key)
            reveal_window(window)

        def refresh_midi(self):
            current = self.midi_choice.get()
            ports, error, backend = detect_midi(module.mido)
            self.atmo_midi_error = error
            self.atmo_midi_backend = backend
            self.midi_cb['values'] = ['Sense MIDI', *ports]
            selected = current if current in ports else (ports[0] if len(ports) == 1 else 'Sense MIDI')
            self.midi_choice.set(selected)
            if error:
                text = ('No s’ha pogut llegir MIDI. loopMIDI pot estar obert; '
                        'comprova el controlador d’aquest Python.\n' + error)
            elif not ports:
                text = 'MIDI: cap port de sortida detectat. Comprova que loopMIDI tingui un port creat i prem Actualitzar ports.'
            elif self.midi is not None:
                text = 'MIDI: connexió existent conservada. Ports: ' + ', '.join(ports)
            else:
                text = 'MIDI detectat: ' + ', '.join(ports) + '. Tria el port i prem Connectar.'
            self.status.set(text)
            self.midi_indicator.config(text='MIDI: error de detecció' if error else
                                       ('MIDI: connectat' if self.midi is not None else 'MIDI: pendent de connexió'))
            return ports

        def connect_midi(self):
            requested = self.midi_choice.get()
            if requested == 'Sense MIDI':
                return super().connect_midi()
            ports = self.refresh_midi()
            self.midi_choice.set(requested if requested in ports else 'Sense MIDI')
            if requested not in ports:
                module.messagebox.showerror('ATMO ESFERA FX · MIDI',
                    self.atmo_midi_error or f'El port «{requested}» ja no està disponible. Actualitza els ports i selecciona’l de nou.',
                    parent=getattr(self, 'atmo_dashboard', self.root))
                return False
            super().connect_midi()
            return self.midi is not None

    # Direct engine callbacks as well as dashboard buttons use these wrappers.
    targets = {'open_zone_editor': 'zone_window', 'open_calibration_editor': 'calibration_window',
               'open_local_audio': 'audio_window', 'open_rules': 'rules_window',
               'open_participants': 'participant_window', 'open_simulator': 'simulator_window',
               'open_projection': 'projection', 'open_midi_diagnostics': 'diagnostics_window',
               'open_audio_settings': 'audio_settings_window', 'open_mute_settings': 'mute_settings_window',
               'open_cc_settings': 'cc_settings_window', 'open_music_settings': 'music_settings_window'}
    def wrap(method, attribute):
        @functools.wraps(method)
        def opened(self, *args, **kwargs):
            result = method(self, *args, **kwargs)
            reveal_window(getattr(self, attribute, None))
            return result
        return opened
    for method, attribute in targets.items():
        if hasattr(original, method): setattr(AtmoApp, method, wrap(getattr(original, method), attribute))
    return AtmoApp
