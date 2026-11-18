"""ATMO presentation and window/MIDI adapters; no project format changes."""
import functools
import sys
import tkinter as tk
from tkinter import ttk
from atmo_windows import dark_titlebar

BG = '#080e20'
PANEL = '#121f39'
SURFACE = '#1a2c49'
TEXT = '#f2f6ff'
MUTED = '#b4c4dd'
CYAN = '#4ce2e0'
PURPLE = '#a78bfa'


def title_atmo(text):
    text = text.replace('ATMO ESFERA FX', 'ATMO ESFERA FX').replace('ATMO ESFERA FX', 'ATMO ESFERA FX')
    return text if text.startswith('ATMO ESFERA FX') else 'ATMO ESFERA FX · ' + text


# Visual system: presentation only. Keep Canvas graphics and projection pixels untouched.
FONT = 'Segoe UI' if sys.platform=='win32' else 'Helvetica'
SUCCESS = '#72dfa8'
DANGER = '#ef899b'
FOCUS = '#4ce2e0'


def configure_theme(root):
    """Apply a consistent ttk palette, including focus, selection and disabled states."""
    style = ttk.Style(root)
    try:
        style.theme_use('clam')  # Required for reliable field/button colours on Windows.
    except tk.TclError:
        pass
    style.configure('.', background=BG, foreground=TEXT, font=(FONT, 10))
    style.configure('TFrame', background=BG)
    style.configure('Card.TFrame', background=PANEL)
    style.configure('Surface.TFrame', background=SURFACE)
    style.configure('TLabel', background=BG, foreground=TEXT)
    style.configure('Muted.TLabel', background=BG, foreground=MUTED)
    style.configure('Title.TLabel', background=BG, foreground=TEXT, font=(FONT, 17, 'bold'))
    style.configure('Section.TLabel', background=BG, foreground=CYAN, font=(FONT, 11, 'bold'))
    style.configure('TLabelFrame', background=BG, bordercolor=SURFACE, relief='flat', borderwidth=1)
    style.configure('TLabelFrame.Label', background=BG, foreground=CYAN, font=(FONT, 10, 'bold'))
    for name in ('TCheckbutton','TRadiobutton'):
        style.configure(name, background=BG, foreground=TEXT, padding=(3, 5))
        style.map(name, background=[('active', BG)], foreground=[('disabled', MUTED)])
    buttons = {
        'TButton': (SURFACE, TEXT),
        'Secondary.TButton': (SURFACE, TEXT),
        'Accent.TButton': (CYAN, BG),
        'Danger.TButton': (DANGER, BG),
    }
    for name, (background, foreground) in buttons.items():
        style.configure(name, background=background, foreground=foreground,
                        padding=(13, 9), borderwidth=1, bordercolor=SURFACE,
                        relief='flat', font=(FONT, 10, 'bold'))
        style.map(name,
            background=[('disabled', PANEL), ('pressed', PURPLE), ('active', PURPLE)],
            foreground=[('disabled', MUTED), ('pressed', BG), ('active', BG)],
            bordercolor=[('focus', FOCUS), ('active', CYAN)])
    for name in ('TEntry', 'TCombobox', 'TSpinbox'):
        style.configure(name, fieldbackground=SURFACE, background=SURFACE,
                        foreground=TEXT, insertcolor=TEXT, arrowcolor=CYAN,
                        bordercolor=SURFACE, lightcolor=SURFACE, darkcolor=SURFACE,
                        padding=(8, 6))
        style.map(name,
            fieldbackground=[('disabled', PANEL), ('readonly', SURFACE)],
            foreground=[('disabled', MUTED), ('readonly', TEXT)],
            bordercolor=[('focus', CYAN)])
    style.configure('Treeview', background=PANEL, fieldbackground=PANEL,
                    foreground=TEXT, bordercolor=SURFACE, rowheight=30, font=(FONT, 10))
    style.configure('Treeview.Heading', background=SURFACE, foreground=CYAN,
                    padding=(8, 8), font=(FONT, 10, 'bold'))
    style.map('Treeview', background=[('selected', CYAN)], foreground=[('selected', BG)])
    style.configure('TNotebook', background=BG, borderwidth=0, tabmargins=(2, 4, 2, 0))
    style.configure('TNotebook.Tab', background=SURFACE, foreground=TEXT, padding=(15, 9),
                    font=(FONT, 10))
    style.map('TNotebook.Tab', background=[('selected', PANEL), ('active', SURFACE)],
              foreground=[('selected', CYAN), ('disabled', MUTED)])
    for orient in ('Vertical', 'Horizontal'):
        style.configure(orient+'.TScrollbar', background=SURFACE, troughcolor=BG,
                        arrowcolor=CYAN, bordercolor=BG, gripcount=0)
        style.map(orient+'.TScrollbar', background=[('active', PURPLE)])
    style.configure('TScale', background=SURFACE,troughcolor=BG,lightcolor=SURFACE,darkcolor=SURFACE,bordercolor=SURFACE)
    for orientation in ('Horizontal','Vertical'):
        style.configure(orientation+'.TScale',background=SURFACE,troughcolor=BG,lightcolor=SURFACE,darkcolor=SURFACE,bordercolor=SURFACE)
    style.configure('TProgressbar', background=CYAN, troughcolor=SURFACE)
    style.configure('Atmo.Treeview',background=PANEL,fieldbackground=PANEL,foreground=TEXT,rowheight=30)
    style.configure('Atmo.Treeview.Heading',background=SURFACE,foreground=CYAN)
    from tkinter import font as tkfont
    for name in ('TkDefaultFont','TkTextFont','TkMenuFont','TkHeadingFont','TkSmallCaptionFont','TkCaptionFont','TkTooltipFont','TkIconFont'):
        try:tkfont.nametofont(name,root=root).configure(family=FONT)
        except tk.TclError:pass
    for pattern, value in {
        '*Font': (FONT,10),
        '*TCombobox*Listbox.background': SURFACE,
        '*TCombobox*Listbox.foreground': TEXT,
        '*TCombobox*Listbox.selectBackground': CYAN,
        '*TCombobox*Listbox.selectForeground': BG,
        '*Menu.background': PANEL,
        '*Menu.foreground': TEXT,
        '*Menu.activeBackground': SURFACE,
        '*Menu.activeForeground': CYAN,
    }.items():
        root.option_add(pattern, value)


def _colour(value):
    return str(value).lower()


def _is_legacy_chrome(value):
    """Only replace known legacy/default chrome; never replace arbitrary semantic colours."""
    return _colour(value) in {
        '#171411','#151210','#261c16','#211913','#2c211a','#36271d',
        '#f0f0f0','#f0f0ed','#d9d9d9','#ececec','#ffffff','white',
        'systembuttonface','systemwindow', 'systemmenu', '#1c120e','#1e1712','#0d0b0b','#241d18','#1a1714','#2b1e16',
        '#e9d8c2','#e0c3a0','#9e805b','#d2a36d','#f4d08d','#edbc88','#f0d9b5',
        '#0b1224','#16243d','#203452'
    }


def theme_widgets(widget):
    """Apply visual chrome recursively, leaving Canvas imagery, media and indicators intact."""
    try:
        kind = widget.winfo_class()
        options = set(widget.keys())
        if kind in ('Tk', 'Toplevel'):
            widget.title(title_atmo(widget.title()))
            dark_titlebar(widget)
            if sys.platform == 'win32' and not getattr(widget, '_atmo_caption_bound', False):
                widget.bind('<Map>', lambda event, w=widget: dark_titlebar(w)
                            if event.widget is w else None, add='+')
                widget._atmo_caption_bound = True
        # Preserve Canvas colours, including the calibrated map, projection and video.
        if kind == 'Canvas':
            if _colour(widget.cget('background')) in ('#171411','#151210','#261c16'):
                widget.configure(background=BG)
        elif kind in ('Tk','Toplevel','Frame','Labelframe','Label','Button',
                      'Checkbutton','Radiobutton','Entry','Spinbox','Text','Scale','Menu','Listbox'):
            config = {}
            if 'background' in options and _is_legacy_chrome(widget.cget('background')):
                config['background'] = SURFACE if kind in ('Button','Entry','Spinbox','Text','Listbox') else PANEL if _colour(widget.cget('background')) in ('#16243d','#261c16') else BG
            if 'foreground' in options and (_is_legacy_chrome(widget.cget('foreground')) or kind in ('Entry','Spinbox','Text','Listbox')):
                config['foreground'] = TEXT
            if 'font' in options:
                try:
                    from tkinter import font as tkfont
                    current = tkfont.Font(root=widget, font=widget.cget('font'))
                    family = str(current.actual('family')).lower()
                    if family not in ('segoe ui',):
                        config['font'] = (FONT, max(9, int(current.cget('size'))),
                                          'bold' if current.actual('weight') == 'bold' else 'normal')
                except (tk.TclError, ValueError, TypeError):
                    pass
            if 'highlightbackground' in options and kind not in ('Tk','Toplevel'):
                config['highlightbackground'] = SURFACE
            if 'highlightcolor' in options: config['highlightcolor'] = CYAN
            if 'insertbackground' in options: config['insertbackground'] = TEXT
            if 'activeforeground' in options: config['activeforeground'] = TEXT
            if 'activebackground' in options and kind != 'Menu': config['activebackground'] = SURFACE
            if 'selectcolor' in options and kind in ('Checkbutton','Radiobutton'):
                config['selectcolor'] = SURFACE
            if 'readonlybackground' in options: config['readonlybackground'] = SURFACE
            if 'disabledbackground' in options:config['disabledbackground']=PANEL
            if 'disabledforeground' in options:config['disabledforeground']=MUTED
            if 'troughcolor' in options:config['troughcolor']=SURFACE
            if kind=='Scale':config.update(background=BG,activebackground=PURPLE,sliderrelief='flat')
            if config: widget.configure(**config)
        if kind.startswith('T') and 'font' in options and widget.cget('font'):
            from tkinter import font as tkfont
            current=tkfont.Font(root=widget,font=widget.cget('font'))
            widget.configure(font=(FONT,max(9,int(current.cget('size'))),current.cget('weight')))
        for child in widget.winfo_children():
            theme_widgets(child)
    except tk.TclError:
        return


def install_window_theme(root):
    """Style newly mapped tool windows, including those created outside the main adapter."""
    configure_theme(root)
    if getattr(root, '_atmo_theme_installed', False):
        return
    root._atmo_theme_installed = True
    pending = set()
    def mapped(event):
        window = event.widget
        if not hasattr(window,'winfo_class'):return
        try:
            if window.winfo_class() not in ('Tk', 'Toplevel') or window in pending:
                return
            pending.add(window)
            def finish():
                pending.discard(window)
                if window.winfo_exists(): theme_widgets(window)
            window.after_idle(finish)
        except tk.TclError:
            pass
    root.bind_all('<Map>', mapped, add='+')

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
            from atmo_ui import build_workspace
            self.workspace_home=build_workspace(self)
            install_window_theme(self.root)
            self.midi_cb.unbind('<<ComboboxSelected>>')
            theme_widgets(self.root)
            self.root.title('ATMO ESFERA FX · Eines completes')

        def show_runtime_info(self):
            module.messagebox.showinfo('ATMO ESFERA FX · Versió i fitxer',
                'Integració ' + str(getattr(self, 'atmo_integration_version', 12)) + ' · Motor ' + module.APP_VERSION + '\nPython: ' + sys.executable,
                parent=getattr(self, 'atmo_dashboard', self.root))

        def resize_banner(self, event):
            from atmo_ui import draw_banner
            draw_banner(self,event)

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
            if self.midi is not None and hasattr(self,'apply_all_volumes'):self.apply_all_volumes()
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
