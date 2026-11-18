"""ATMO ESFERA FX · Integració 19: entrada directa a les eines principals."""
import importlib.util
import sys
from pathlib import Path
import tkinter as tk
from tkinter import messagebox
from atmo_esfera_fx_integracio_12 import AtmoZoneEditor, label, btn, BG, PANEL, TEXT, MUTED, CYAN, PURPLE, MODES
from atmo_primary import primary_engine
from atmo_windows import maximize_window
from atmo_runtime import theme_widgets, configure_theme, install_window_theme, SURFACE
from PIL import Image, ImageTk, ImageOps
from atmo_ui import wrap_card_text

BASE = Path(__file__).resolve().parent
ENGINE = BASE / 'atmo_esfera_fx_4_5_15_pas_15_editor_musical_desplegable.py'


def open_engine(mode, game_action=None):
    root = None
    try:
        if not ENGINE.is_file():
            raise FileNotFoundError('Falta el motor ATMO. Extreu la carpeta completa del programa.')
        spec = importlib.util.spec_from_file_location('atmo_engine_19', ENGINE)
        if spec is None or spec.loader is None:
            raise RuntimeError('No es pot carregar el motor ATMO.')
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        module.ZoneEditor = AtmoZoneEditor
        root = tk.Tk()
        root.withdraw()
        app = primary_engine(module, mode)(root)
        app.atmo_experience_mode = mode
        app.atmo_integration_version = 19
        root.title('ATMO ESFERA FX · ' + mode)
        root.deiconify()
        maximize_window(root)
        def start_project():
            try:
                if game_action == 'new': app.new_project()
                elif game_action in ('open', 'template'): app.open_project()
            finally:
                app.finish_startup()
        root.after_idle(start_project)
        root.mainloop()
    except Exception as exc:
        messagebox.showerror('ATMO ESFERA FX', 'Error en iniciar ATMO:\n' + str(exc), parent=root)


def main():
    splash=tk.Tk(); splash.title('ATMO ESFERA FX · Inici')
    splash.geometry('1280x760'); splash.minsize(940,620); splash.configure(bg=BG)
    install_window_theme(splash); theme_widgets(splash); maximize_window(splash)
    selected={'mode':None,'game_action':None}; images=[]
    def clear():
        images.clear()
        for child in splash.winfo_children(): child.destroy()
    def header(subtitle):
        band=tk.Frame(splash,bg=BG); band.pack(fill='x',padx=35,pady=(20,12))
        path=BASE/'atmo_assets'/'atmo_logo.png'
        if path.is_file():
            try:
                with Image.open(path) as im: photo=ImageTk.PhotoImage(im.resize((65,65),Image.Resampling.LANCZOS),master=splash)
                images.append(photo);tk.Label(band,image=photo,bg=BG).pack(side='left',padx=(0,14))
            except (OSError,tk.TclError): pass
        titles=tk.Frame(band,bg=BG);titles.pack(side='left')
        label(titles,'ATMO ESFERA FX',27,bold=True).pack(anchor='w')
        label(titles,subtitle,12,MUTED).pack(anchor='w')
        tk.Frame(splash,bg=SURFACE,height=1).pack(fill='x',padx=35)
    def choose(mode):
        clear();splash.title('ATMO ESFERA FX · '+mode+' · Projecte')
        header('Una experiència comença amb un projecte')
        label(splash,mode.upper()+' · TRIA EL PROJECTE',20,CYAN,True).pack(pady=(35,10))
        label(splash,'Selecciona com vols començar. Després s’obrirà l’editor.',11,MUTED).pack(pady=(0,18))
        options=tk.Frame(splash,bg=PANEL,padx=30,pady=20);options.pack(pady=8)
        def proceed(action):
            selected['mode']=mode;selected['game_action']=action;splash.destroy()
        for title,action,primary in (('+  Projecte nou','new',True),('Obrir un projecte existent','open',False),('Triar una plantilla','template',False),('Entrar a l’editor sense carregar cap projecte',None,False)):
            btn(options,title,lambda a=action:proceed(a),primary).pack(fill='x',pady=6)
        btn(splash,'← Tornar a les experiències',show_start).pack(pady=15)
    def show_start():
        clear(); splash.title('ATMO ESFERA FX · Inici')
        header('L’espai es converteix en instrument')
        label(splash,'Tria el teu univers',22,bold=True).pack(pady=(8,12))
        row=tk.Frame(splash,bg=BG)
        row.pack(fill='both',expand=True,padx=20,pady=(0,20))
        subtitles=('Experiències interactives','Composició i control sonor',
                   'Continguts i recorreguts visuals','Espais immersius reactius')
        names=('joc','musica','exposicio','immersiva')
        for idx,(mode,subtitle,name) in enumerate(zip(MODES,subtitles,names)):
            row.grid_columnconfigure(idx,weight=1,uniform='mode')
            card=tk.Frame(row,bg=PANEL,padx=6,pady=7,highlightthickness=1,
                          highlightbackground=SURFACE)
            card.grid(row=0,column=idx,sticky='nsew',padx=5)
            # La imatge és el contingut principal; la seva mida segueix la targeta.
            artwork=tk.Label(card,bg=SURFACE,bd=0,cursor='hand2')
            artwork.pack(fill='both',expand=True,pady=(0,9))
            artwork.bind('<Button-1>',lambda event,m=mode:choose(m))
            path=BASE/'atmo_assets'/('atmo_'+name+'.png')
            try:
                with Image.open(path) as source:
                    original=source.convert('RGB').copy()
            except (OSError,ValueError):
                original=None
            cache={'size':None,'image':None,'job':None}
            def redraw(event=None, target=artwork, source=original, state=cache):
                if not target.winfo_exists(): return
                width=max(160,target.winfo_width())
                height=max(140,target.winfo_height())
                size=(width,height)
                if size==state['size']: return
                state['size']=size
                if source is not None:
                    thumb=ImageOps.fit(source,size,method=Image.Resampling.LANCZOS,
                                       centering=(.5,.5))
                    photo=ImageTk.PhotoImage(thumb,master=splash)
                    state['image']=photo
                    target.configure(image=photo,text='')
                else:
                    target.configure(image='',text='✧',fg=CYAN,
                                     font=('Segoe UI',44),bg=SURFACE)
            def schedule(event, target=artwork, state=cache, source=original):
                if state['job'] is not None:
                    try: target.after_cancel(state['job'])
                    except tk.TclError: pass
                state['job']=target.after(90,lambda: redraw(target=target,source=source,state=state))
            artwork.bind('<Configure>',schedule)
            footer=tk.Frame(card,bg=PANEL);footer.pack(side='bottom',fill='x',before=artwork)
            label(footer,mode,16,bold=True,wraplength=260).pack(pady=(0,3))
            label(footer,subtitle,10,MUTED,wraplength=250).pack(pady=(0,8))
            btn(footer,'Entrar a '+mode,lambda m=mode:choose(m),True).pack(fill='x',pady=(0,2))
            wrap_card_text(footer)
        row.grid_rowconfigure(0,weight=1)
    show_start();splash.mainloop()
    if selected['mode']:open_engine(selected['mode'],selected['game_action'])

if __name__=="__main__":main()

