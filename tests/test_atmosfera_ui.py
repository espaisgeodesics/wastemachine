import hashlib,json,os
from pathlib import Path
from types import SimpleNamespace
import unittest
import tkinter as tk
from tkinter import ttk
from atmo_runtime import install_window_theme,theme_widgets,BG,SURFACE,TEXT
from spatial_calibration import CalibrationEditor

ROOT=Path(__file__).resolve().parents[1]

class ApprovedAssetsTests(unittest.TestCase):
    def test_four_approved_artworks_are_unchanged(self):
        manifest=json.loads((ROOT/'atmo_assets'/'APROVACIO_IMATGES.json').read_text())
        self.assertEqual(len(manifest),4)
        for name,expected in manifest.items():self.assertEqual(hashlib.sha256((ROOT/'atmo_assets'/name).read_bytes()).hexdigest(),expected)

class ForestPaletteTests(unittest.TestCase):
    def test_readable_text_and_natural_accents(self):
        from atmo_runtime import BG,PANEL,SURFACE,TEXT,MUTED,LEAF,FOREST
        def light(color):
            values=[int(color[i:i+2],16)/255 for i in (1,3,5)]
            values=[v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in values]
            return sum(v*w for v,w in zip(values,(.2126,.7152,.0722)))
        for foreground,background in ((TEXT,BG),(TEXT,PANEL),(TEXT,SURFACE),(TEXT,FOREST),(MUTED,BG),(LEAF,BG),(BG,LEAF)):
            a,b=sorted((light(foreground),light(background)))
            self.assertGreaterEqual((b+.05)/(a+.05),4.5,(foreground,background))

@unittest.skipUnless(os.environ.get('DISPLAY') or os.name=='nt','Graphical display required')
class VisualRegressionTests(unittest.TestCase):
    def setUp(self):
        self.root=tk.Tk();self.errors=[]
        self.root.report_callback_exception=lambda typ,value,tb:self.errors.append(str(value))
        self.root.geometry('1000x700');install_window_theme(self.root)
    def tearDown(self):
        for timer in self.root.tk.call('after','info'):self.root.tk.call('after','cancel',timer)
        self.root.destroy()
    def children(self,widget):
        for child in widget.winfo_children():yield child;yield from self.children(child)
    def test_inputs_remain_readable_and_projector_black_is_preserved(self):
        field=tk.Spinbox(self.root);field.pack()
        projection=tk.Label(self.root,bg='black');projection.pack()
        canvas=tk.Canvas(self.root,bg='black');canvas.pack()
        theme_widgets(self.root)
        self.assertEqual(field.cget('background'),SURFACE);self.assertEqual(field.cget('foreground'),TEXT)
        self.assertEqual(projection.cget('background'),'black');self.assertEqual(canvas.cget('background'),'black')
    def test_window_theme_is_idempotent_and_combobox_popup_does_not_crash(self):
        install_window_theme(self.root);before=self.root.bind_all('<Map>');install_window_theme(self.root)
        self.assertEqual(self.root.bind_all('<Map>'),before)
        combo=ttk.Combobox(self.root,values=['Cap','Imatge / Vídeo'],state='readonly');combo.pack();combo.set('Cap');self.root.update()
        self.root.tk.call('ttk::combobox::Post',str(combo));self.root.update()
        self.root.tk.call('ttk::combobox::Unpost',str(combo));self.root.update()
        self.assertFalse(self.errors);self.assertEqual(combo.get(),'Cap')
    def test_dark_menu_reuses_original_commands(self):
        from atmo_ui import install_menu_bar
        from unittest.mock import Mock
        command=Mock();menu=tk.Menu(self.root);sub=tk.Menu(menu,tearoff=False)
        sub.add_command(label='Desar',command=command);menu.add_cascade(label='Projecte',menu=sub)
        self.root.configure(menu=menu)
        banner=tk.Canvas(self.root);banner.pack()
        app=SimpleNamespace(root=self.root,banner_canvas=banner)
        install_menu_bar(app);self.root.update()
        self.assertEqual(self.root.cget('menu'),'')
        button=app.atmo_menu_bar.winfo_children()[0]
        self.assertEqual(str(button.cget('menu')),str(sub))
        sub.invoke(0);command.assert_called_once()

    def test_long_experience_action_wraps_at_high_dpi(self):
        from atmo_ui import wrap_card_text
        self.root.tk.call('tk','scaling',2.)
        card=tk.Frame(self.root,width=210,height=180);card.pack();card.pack_propagate(False)
        button=tk.Button(card,text='Entrar a Instal·lació immersiva',font=('Segoe UI',15),padx=12)
        button.pack(fill='x');wrap_card_text(card);self.root.update()
        self.assertLessEqual(button.winfo_reqwidth(),card.winfo_width())
        self.assertGreater(button.winfo_reqheight(),30)

    def test_calibration_apply_remains_visible_at_all_font_scales(self):
        for scale in (1.,1.25,1.5):
            self.root.tk.call('tk','scaling',96/72*scale)
            window=tk.Toplevel(self.root);window.geometry('920x650')
            CalibrationEditor(window,lambda:(None,0),lambda:0,lambda:None,lambda c:True)
            self.root.update()
            button=next(w for w in self.children(window) if w.winfo_class()=='TButton' and w.cget('text')=='APLICAR CALIBRACIÓ')
            self.assertTrue(button.winfo_ismapped())
            self.assertLessEqual(button.winfo_rooty()+button.winfo_height(),window.winfo_rooty()+window.winfo_height())
            window.destroy()
        self.assertFalse(self.errors)

if __name__=='__main__':unittest.main()
