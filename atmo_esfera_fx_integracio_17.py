"""ATMO ESFERA FX · Integració 17: entrada directa a les eines principals."""
import importlib.util
import sys
from pathlib import Path
import tkinter as tk
from tkinter import messagebox
from atmo_esfera_fx_integracio_12 import AtmoZoneEditor, label, btn, BG, PANEL, TEXT, MUTED, CYAN, PURPLE, MODES
from atmo_primary import primary_engine
from atmo_windows import maximize_window
from atmo_runtime import theme_widgets

BASE = Path(__file__).resolve().parent
ENGINE = BASE / 'atmo_esfera_fx_4_5_15_pas_15_editor_musical_desplegable.py'


def open_engine(mode, game_action=None):
    root = None
    try:
        if not ENGINE.is_file():
            raise FileNotFoundError('Falta el motor ATMO. Extreu la carpeta completa del programa.')
        spec = importlib.util.spec_from_file_location('atmo_engine_17', ENGINE)
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
        app.atmo_integration_version = 17
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
    splash=tk.Tk();splash.title("ATMO ESFERA FX · Inici")
    splash.geometry("1100x690");splash.minsize(940,620);splash.configure(bg=BG)
    theme_widgets(splash)
    maximize_window(splash)
    selected={"mode":None,"game_action":None}
    label(splash,"ATMO ESFERA FX",32,bold=True).pack(pady=(52,5))
    label(splash,"L'espai es converteix en instrument",13,MUTED).pack()
    label(splash,"Què vols crear?",18,bold=True).pack(pady=(38,20))
    row=tk.Frame(splash,bg=BG);row.pack(fill="both",expand=True,padx=30,pady=(0,30))
    subtitles=("Experiències interactives","Composició i control sonor","Continguts i recorreguts visuals","Espais immersius reactius")
    colors=(CYAN,PURPLE,"#f7c27a","#80c5f7")
    def choose(mode):
        # Pantalla 2 obligatòria per a TOTS els modes; el motor encara no s'ha creat.
        for child in splash.winfo_children():
            child.destroy()
        splash.title("ATMO ESFERA FX · "+mode+" · Projecte")
        label(splash,"ATMO ESFERA FX",29,bold=True).pack(pady=(45,7))
        label(splash,mode.upper()+" · TRIA EL PROJECTE",19,CYAN,True).pack(pady=(6,10))
        label(splash,"Primer selecciona com vols començar. Després s'obrirà l'editor.",11,MUTED).pack(pady=(0,23))
        options=tk.Frame(splash,bg=BG);options.pack(pady=8)
        def proceed(action):
            selected["mode"]=mode
            selected["game_action"]=action
            splash.destroy()
        btn(options,"+  Projecte nou",lambda:proceed("new"),True).pack(fill="x",pady=7)
        btn(options,"Obrir un projecte existent",lambda:proceed("open")).pack(fill="x",pady=7)
        btn(options,"Triar una plantilla",lambda:proceed("template")).pack(fill="x",pady=7)
        btn(options,"Entrar a l'editor sense carregar cap projecte",lambda:proceed(None)).pack(fill="x",pady=7)
        btn(splash,"← Tornar a les experiències",lambda:show_start()).pack(pady=12)

    def show_start():
        for child in splash.winfo_children():child.destroy()
        splash.title("ATMO ESFERA FX · Inici")
        label(splash,"ATMO ESFERA FX",32,bold=True).pack(pady=(52,5))
        label(splash,"L'espai es converteix en instrument",13,MUTED).pack()
        label(splash,"Què vols crear?",18,bold=True).pack(pady=(38,20))
        row=tk.Frame(splash,bg=BG);row.pack(fill="both",expand=True,padx=30,pady=(0,30))
        subtitles=("Experiències interactives","Composició i control sonor","Continguts i recorreguts visuals","Espais immersius reactius")
        colors=(CYAN,PURPLE,"#f7c27a","#80c5f7")
        for idx,(mode,subtitle,color) in enumerate(zip(MODES,subtitles,colors)):
            card=tk.Frame(row,bg=PANEL,padx=13,pady=15)
            card.grid(row=0,column=idx,sticky="nsew",padx=6)
            # Reservem primer el botó inferior: no es tallarà si el subtítol
            # ocupa dues línies (com passa a Exposició).
            btn(card,"Entrar",lambda m=mode:choose(m),True).pack(side="bottom",fill="x",pady=(8,0))
            row.grid_columnconfigure(idx,weight=1);row.grid_rowconfigure(0,weight=1)
            art=tk.Canvas(card,width=180,height=155,bg=PANEL,highlightthickness=0)
            art.pack(fill="x",pady=(8,12))
            if idx==0:
                for x,y in [(35,40),(145,40),(35,120),(145,120)]:art.create_oval(x-13,y-13,x+13,y+13,fill=color,outline="")
                art.create_line(35,40,145,120,fill=color,width=3)
                art.create_line(145,40,35,120,fill=color,width=3)
            elif idx==1:
                for j,h in enumerate((32,70,105,55,90,42)):
                    x=24+j*27;art.create_rectangle(x,130-h,x+16,130,fill=color,outline="")
            elif idx==2:
                art.create_oval(26,18,155,146,outline=color,width=5)
                art.create_polygon(90,25,145,110,35,110,fill=color,outline="")
            else:
                for r in (38,65):art.create_oval(90-r,82-r,90+r,82+r,outline=color,width=3)
                for x,y in ((90,18),(155,82),(90,146),(25,82)):art.create_oval(x-6,y-6,x+6,y+6,fill=color,outline="")
            label(card,mode,14,bold=True,wraplength=190).pack(pady=(5,8))
            label(card,subtitle,10,MUTED,wraplength=180).pack(pady=(0,8))

    show_start()
    splash.mainloop()
    if selected["mode"]:open_engine(selected["mode"],selected["game_action"])

if __name__=="__main__":main()

