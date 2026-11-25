"""Capture actual Tk windows on Windows or an existing Linux display.

python -m tools.capturar_atmo [--output VALIDACIO/captures] [--scales 1 1.25 1.5]
Uses synthetic camera/notes and no MIDI port or physical audio device.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import platform
import sys
import time
import tkinter as tk
from tkinter import font
from unittest.mock import patch
import numpy as np
from PIL import ImageGrab

ROOT=Path(__file__).resolve().parents[1]

def widgets(parent):
    for child in parent.winfo_children():
        yield child
        yield from widgets(child)

def rectangle(window):
    if sys.platform=='win32':
        import ctypes
        from ctypes import wintypes
        rect=wintypes.RECT();user=ctypes.windll.user32
        handle=user.GetAncestor(window.winfo_id(),2)
        if user.GetWindowRect(handle,ctypes.byref(rect)):return rect.left,rect.top,rect.right,rect.bottom
    x,y=window.winfo_rootx(),window.winfo_rooty()
    return x,y,x+window.winfo_width(),y+window.winfo_height()

def run(output,scales):
    from atmo_primary import primary_engine
    from atmo_esfera_fx_integracio_12 import AtmoZoneEditor
    from spatial_zones import SpatialMap,Calibration
    from atmo_runtime import install_window_theme
    output.mkdir(parents=True,exist_ok=True)
    report=dict(platform=platform.platform(),python=sys.version,display=os.environ.get('DISPLAY'),scales={},errors=[])
    def pump(root):
        for _ in range(5):root.update();time.sleep(.035)
    def save(root,window,path):
        for child in root.winfo_children():
            if isinstance(child,tk.Toplevel) and child is not window:child.withdraw()
        window.deiconify();window.lift();window.focus_set();pump(root)
        if sys.platform=='win32':image=ImageGrab.grab(rectangle(window),all_screens=True)
        else:image=ImageGrab.grab(rectangle(window),xdisplay=os.environ.get('DISPLAY'))
        image.save(path)
    # Exercise the approved entry screen and project screen through actual buttons.
    import atmo_esfera_fx_integracio_19 as entry
    actual_tk=tk.Tk
    for scale in scales:
        directory=output/str(round(scale*100));directory.mkdir(exist_ok=True)
        def make_splash():
            root=actual_tk();root.tk.call('tk','scaling',96/72*scale)
            root.report_callback_exception=lambda typ,value,tb:report['errors'].append('entry: '+str(value))
            def shot():
                root.state('normal');root.geometry(f'{min(1600,root.winfo_screenwidth()-30)}x{min(980,root.winfo_screenheight()-60)}+10+10')
                pump(root);save(root,root,directory/'01_inici.png')
                button=next(w for w in widgets(root) if w.winfo_class()=='Button' and w.cget('text')=='Entrar a Música')
                button.invoke();pump(root);save(root,root,directory/'02_projecte.png');root.destroy()
            root.after(650,shot)
            return root
        with patch.object(entry.tk,'Tk',side_effect=make_splash):entry.main()
        spec=importlib.util.spec_from_file_location('atmo_capture_engine',ROOT/'atmo_esfera_fx_4_5_15_pas_15_editor_musical_desplegable.py')
        module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
        module.ZoneEditor=AtmoZoneEditor
        root=actual_tk();root.tk.call('tk','scaling',96/72*scale)
        root.report_callback_exception=lambda typ,value,tb:report['errors'].append(str(value))
        with patch('atmo_runtime.detect_midi',return_value=((),None,'mido.backends.rtmidi')),patch.object(module.mido,'get_output_names',return_value=[]):
            app=primary_engine(module,'Joc')(root)
        app.arp_stop.set();app.arp_thread.join(1);app.finish_startup();root.state('normal')
        root.geometry(f'{min(1500,root.winfo_screenwidth()-30)}x{min(940,root.winfo_screenheight()-60)}+10+10');pump(root)
        report['scales'][str(scale)]=dict(tk=root.tk.call('info','patchlevel'),scaling=float(root.tk.call('tk','scaling')),segoe_available='Segoe UI' in font.families(root),windows=[])
        def capture(name,window):
            window.geometry(f'{min(max(window.winfo_width(),window.winfo_reqwidth()),root.winfo_screenwidth()-60)}x{min(max(window.winfo_height(),window.winfo_reqheight()),root.winfo_screenheight()-90)}+30+30')
            save(root,window,directory/(name+'.png'));report['scales'][str(scale)]['windows'].append(name)
        capture('03_motor',root)
        for key in ('camera','visual','midi','editor','cards','mixer'):
            app.show_panel(key);capture('04_'+key,app.panel_windows[key])
        for kind in ('Harmonia espacial','Arpegiador espacial','Patró rítmic','Ritme de bateria'):
            app.fun.set(kind);app.open_music_settings();capture('05_'+kind.replace(' ','_'),app.music_settings_window)
        for name,kind,method,attribute in (
            ('06_ambients','Chaos Oscillator (Kaoss XY)','open_kaoss_settings','kaoss_window'),
            ('07_visual_fitxer','Canviar visual','open_card_media_settings','media_window'),
            ('08_audio_midi','Àudio','open_audio_settings','audio_settings_window'),
            ('09_cc','Control MIDI CC','open_cc_settings','cc_settings_window'),
            ('10_mute','Control d’àudio / Mute','open_mute_settings','mute_settings_window'),
            ('11_nota','Nota MIDI','open_basic_function_settings','basic_function_window'),
            ('12_zones',None,'open_zone_editor','zone_window'),
            ('13_calibracio',None,'open_calibration_editor','calibration_window'),
            ('14_audio_local',None,'open_local_audio','audio_window'),
            ('15_diagnosi',None,'open_midi_diagnostics','diagnostics_window'),
            ('16_participants',None,'open_participants','participant_window'),
            ('17_regles',None,'open_rules','rules_window'),
            ('18_simulador',None,'open_simulator','simulator_window'),
            ('19_projector',None,'open_projection','projection')):
            try:
                if kind:app.fun.set(kind)
                getattr(app,method)();capture(name,getattr(app,attribute))
                if name=='06_ambients':
                    app.kaoss_editor.load_bus_profile()
                    capture('06b_XY_Cakewalk',app.kaoss_window)
                    for canvas in (w for w in widgets(app.kaoss_window) if w.winfo_class()=='Canvas' and w.cget('yscrollcommand')):canvas.yview_moveto(1.)
                    capture('06c_XY_proves',app.kaoss_window)
                if name=='10_mute':
                    app.mute_fade_enabled.set(True)
                    capture('10b_fades',app.mute_settings_window)
                    for canvas in (w for w in widgets(app.mute_settings_window) if w.winfo_class()=='Canvas' and w.cget('yscrollcommand')):canvas.yview_moveto(1.)
                    capture('10c_fades_ajuda',app.mute_settings_window)
                if name=='12_zones' and hasattr(app.zone_editor,'audio_status'):
                    canvases=[w for w in widgets(app.zone_window) if w.winfo_class()=='Canvas' and w.cget('yscrollcommand')]
                    for canvas in canvases:canvas.yview_moveto(.52)
                    capture('12_zones_so',app.zone_window)
                    for canvas in canvases:canvas.yview_moveto(1.)
                    capture('12_zones_final',app.zone_window)
            except Exception as exc:report['errors'].append(name+': '+str(exc))
        # A calibrated operator map with synthetic positions, no camera or MIDI needed.
        points=((.5,0),(1,.5),(.5,1),(0,.5));app.spatial_map=SpatialMap(calibration=Calibration(points))
        app.cards[0]['function']='Harmonia espacial';app.cards[1]['function']='Arpegiador espacial'
        app.cards[1].update(arp_map='grid',arp_note_count=5)
        app.active={0:(.4,.4,0),1:(.7,.6,.2)};app.preview_card=0;app.visual_dirty=True;app.preview_dirty=True
        app.show_panel('visual');pump(root);capture('20_mapa_musical',app.visual_window)
        for editor in (app.zone_editor,app.rules_editor,app.participant_editor):
            if editor is not None:editor.dirty=False
        for timer in root.tk.call('after','info'):root.tk.call('after','cancel',timer)
        with patch.object(module.messagebox,'askyesno',return_value=True):app.close()
    (output/'resultat_captures.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return 1 if report['errors'] else 0

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT/'VALIDACIO'/'captures');parser.add_argument('--scales',nargs='+',type=float,default=[1,1.25,1.5]);args=parser.parse_args()
    sys.exit(run(args.output,args.scales))
