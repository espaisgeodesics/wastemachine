"""ATMO ESFERA FX · Integració 09 (base consolidada).
Interfície de navegació connectada als controls de Wasteland Machine 4.8.1.
No altera ni substitueix el motor, els projectes o les seves dades.
Cal copiar aquest fitxer a la carpeta del projecte complet.
"""
from __future__ import annotations
import importlib.util
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox

BASE = Path(__file__).resolve().parent
ENGINE = BASE / "wasteland_4_5_15_pas_15_editor_musical_desplegable.py"
BG="#0b1224"; PANEL="#16243d"; SURFACE="#203452"
TEXT="#f5f7ff"; MUTED="#a8bad5"; CYAN="#45d4d2"; PURPLE="#9b8cff"
MODES=("Joc","Música","Exposició","Instal·lació immersiva")
SECTIONS=("Espai","Targetes","Accions","Música i àudio","Visuals","Prova","Projectes")

def label(parent, text, size=11, color=TEXT, bold=False, **kwargs):
    return tk.Label(parent,text=text,bg=parent.cget("bg"),fg=color,
                    font=("Segoe UI",size,"bold" if bold else "normal"),**kwargs)

def btn(parent,text,command,accent=False):
    return tk.Button(parent,text=text,command=command,bg=CYAN if accent else SURFACE,
                     fg="#07182a" if accent else TEXT,activebackground=PURPLE,
                     activeforeground="#07182a",font=("Segoe UI",10,"bold"),
                     relief="flat",padx=12,pady=9,cursor="hand2")

def open_engine(mode, game_action=None):
    if not ENGINE.is_file():
        messagebox.showerror("Falta el motor","Cal copiar aquest fitxer a la carpeta completa del projecte,\nal costat de:\n"+ENGINE.name)
        return
    try:
        spec=importlib.util.spec_from_file_location("atmo_engine_09",ENGINE)
        if spec is None or spec.loader is None: raise RuntimeError("No es pot carregar el motor")
        module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        root=tk.Tk()
        # Ocultem el motor ABANS de construir-ne les finestres.
        root.withdraw()
        root.attributes("-alpha",0.0)
        # El motor programa raise_all_panels als 450 ms.
        # Aquest mètode crida default_window_layout(), que torna a
        # mostrar la previsualització malgrat haver-la amagat abans.
        # Desactivem només aquesta obertura AUTOMÀTICA en mode ATMO.
        module.App.raise_all_panels=lambda self: None
        app=module.App(root)
        app.atmo_experience_mode=mode
        root.title("ATMO ESFERA FX · motor "+str(getattr(module,"APP_VERSION","original")))
        # L'editor ATMO és la vista principal; el motor queda disponible en segon pla.
        root.withdraw()
        for window in getattr(app,"panel_windows",{}).values():
            try: window.withdraw()
            except tk.TclError: pass
        workspace=Workspace(root,app,mode)
        workspace.show_section("Projectes")
        if game_action in ("open","template"):
            root.after(750,lambda:workspace.invoke("open_project"))
        elif game_action=="new":
            root.after(750,lambda:workspace.invoke("new_project"))
        # El motor antic intenta aixecar els panells durant l'arrencada.
        # Els amaguem després, sense destruir-los ni aturar el seu funcionament.
        def finish_startup():
            for window in getattr(app,"panel_windows",{}).values():
                try: window.withdraw()
                except tk.TclError: pass
            workspace.win.deiconify()
            workspace.win.lift()
            workspace.win.focus_set()
        root.after(550,finish_startup)
        # Només durant l'arrencada: no interfereix amb panells oberts per l'usuari.
        root.after(650,workspace.suppress_startup_windows)
        root.mainloop()
    except Exception as exc:
        messagebox.showerror("ATMO ESFERA FX","Error en iniciar el motor:\n"+str(exc))


class SpatialGrid(tk.Frame):
    """Vista real del SpatialMap actiu, sense modificar-ne les dades."""
    def __init__(self,parent,workspace):
        super().__init__(parent,bg=PANEL)
        self.workspace=workspace
        self.selected=None
        self.canvas=tk.Canvas(self,bg="#101c30",highlightthickness=0,height=400)
        self.canvas.pack(side="left",fill="both",expand=True,padx=(12,8),pady=12)
        sidebar=tk.Frame(self,bg=PANEL,width=235)
        sidebar.pack(side="right",fill="y",padx=(0,12),pady=12)
        sidebar.pack_propagate(False)
        label(sidebar,"QUADRÍCULA REAL",12,CYAN,True).pack(anchor="w")
        self.info=tk.StringVar(value="Selecciona una casella")
        tk.Label(sidebar,textvariable=self.info,bg=PANEL,fg=TEXT,
                 wraplength=215,justify="left",font=("Segoe UI",10)).pack(anchor="w",pady=12)
        btn(sidebar,"Editar zones",lambda:workspace.invoke("open_zone_editor"),True).pack(fill="x",pady=4)
        btn(sidebar,"Actualitzar",self.draw).pack(fill="x",pady=4)
        btn(sidebar,"Càmera",lambda:workspace.invoke("show_panel","camera")).pack(fill="x",pady=4)
        label(sidebar,"Vista connectada a spatial_map.\nL'edició continua a l'editor original.",9,MUTED,
              justify="left",wraplength=220).pack(anchor="w",pady=18)
        self.canvas.bind("<Configure>",lambda e:self.draw())
        self.canvas.bind("<Button-1>",self.click)
        self.after(1000,self.refresh)

    def refresh(self):
        if not self.winfo_exists():return
        self.draw()
        self.after(1500,self.refresh)

    def draw(self):
        if not self.winfo_exists():return
        m=getattr(self.workspace.app,"spatial_map",None)
        if m is None:
            self.info.set("Aquest motor no exposa spatial_map.")
            return
        rows,cols=m.grid.rows,m.grid.columns
        c=self.canvas
        c.delete("all")
        width=max(220,c.winfo_width());height=max(220,c.winfo_height())
        side=max(140,min(width-40,height-40))
        left=(width-side)/2;top=(height-side)/2
        cell=side/max(rows,cols)
        grid_w=cell*cols;grid_h=cell*rows
        left=(width-grid_w)/2;top=(height-grid_h)/2
        self.bounds=(left,top,cell,rows,cols)
        zone_by_cell={tuple(cell_id):zone for zone in m.zones for cell_id in zone.cells}
        palette=("#277f91","#8565bb","#bc7e4b","#5c9c79","#a75c8b","#8b9d4b")
        colors={z.id:palette[i%len(palette)] for i,z in enumerate(m.zones)}
        for row in range(rows):
            for col in range(cols):
                x1=left+col*cell;y1=top+row*cell
                x2=x1+cell;y2=y1+cell
                eligible=m.grid.eligible((row,col))
                zone=zone_by_cell.get((row,col))
                fill=colors[zone.id] if zone else ("#223b59" if eligible else "#101c30")
                outline=CYAN if self.selected==(row,col) else "#3c5674"
                c.create_rectangle(x1,y1,x2,y2,fill=fill,outline=outline,width=3 if self.selected==(row,col) else 1)
        c.create_oval(left,top,left+grid_w,top+grid_h,outline=CYAN,width=2)
        c.create_text(width/2,13,text=f"{rows} × {cols}  ·  {len(m.zones)} zones",
                      fill=MUTED,font=("Segoe UI",10))
        if self.selected is not None:
            row,col=self.selected
            if row>=rows or col>=cols:self.selected=None
            else:
                zone=zone_by_cell.get((row,col))
                detail=(f"Fila {row+1} · Columna {col+1}\n"+
                        (f"Zona: {zone.name}\nTargetes autoritzades: "+
                         (", ".join(str(n) for n in sorted(zone.authorized_cards)) or "Cap")
                         if zone else "Sense zona assignada"))
                self.info.set(detail)
        else:
            self.info.set(f"Quadrícula {rows} × {cols}\nZones definides: {len(m.zones)}\n\nSelecciona una casella.")

    def click(self,event):
        if not hasattr(self,"bounds"):return
        left,top,cell,rows,cols=self.bounds
        col=int((event.x-left)//cell);row=int((event.y-top)//cell)
        if 0<=row<rows and 0<=col<cols:
            self.selected=(row,col)
            self.draw()

class Workspace:
    def __init__(self,root,app,mode):
        self.root=root; self.app=app; self.mode=mode
        self.win=tk.Toplevel(root)
        self.win.title("ATMO ESFERA FX · "+mode)
        self.win.geometry("1160x760+70+40"); self.win.minsize(850,570)
        self.win.configure(bg=BG)
        self.win.protocol("WM_DELETE_WINDOW",self.win.withdraw)
        app.atmo_dashboard=self.win
        self._allow_auxiliary_windows=False
        self.status=tk.StringVar(value="Preparat · Els controls obren les eines originals")
        head=tk.Frame(self.win,bg=BG);head.pack(fill="x",padx=22,pady=(18,8))
        label(head,"ATMO ESFERA FX",24,bold=True).pack(side="left")
        label(head,"  ·  "+mode,12,MUTED).pack(side="left",padx=10)
        btn(head,"Programa original",self.show_original).pack(side="right")
        nav=tk.Frame(self.win,bg=BG);nav.pack(fill="x",padx=20,pady=8)
        self.nav_buttons={}
        for section in SECTIONS:
            b=btn(nav,section,lambda s=section:self.show_section(s))
            b.pack(side="left",padx=3)
            self.nav_buttons[section]=b
        self.body=tk.Frame(self.win,bg=BG);self.body.pack(fill="both",expand=True,padx=20,pady=8)
        bottom=tk.Frame(self.win,bg=BG);bottom.pack(fill="x",padx=22,pady=(3,14))
        label(bottom,"●",13,CYAN).pack(side="left")
        label(bottom,"Integració 10b · Quadrícula integrada · Motor original preservat",9,MUTED).pack(side="left",padx=7)
        btn(bottom,"SILENCI ABSOLUT",lambda:self.invoke("toggle_panic")).pack(side="right")
        self.show_section("Espai")
        self.win.lift()

    def suppress_startup_windows(self):
        """Amaga finestres auxiliars creades durant l'arrencada, fins i tot amb after()."""
        if self._allow_auxiliary_windows or not self.win.winfo_exists():
            return
        for child in self.root.winfo_children():
            if isinstance(child,tk.Toplevel) and child is not self.win:
                try:
                    if child.winfo_exists(): child.withdraw()
                except tk.TclError:
                    pass

    def show_original(self):
        self.root.attributes("-alpha",1.0);self.root.deiconify();self.root.lift()

    def invoke(self,method,*args):
        self._allow_auxiliary_windows=True
        fn=getattr(self.app,method,None)
        if not callable(fn):
            messagebox.showwarning("Funció no disponible","Aquest motor no exposa l'eina: "+method,parent=self.win)
            return
        try:
            result=fn(*args)
            # Les finestres creades amb make_panel_window són transient(root).
            # Com que ATMO manté root ocult, Windows pot ocultar també la filla.
            # Desvinculem només la finestra sol·licitada i la fem visible.
            if method=="open_zone_editor":
                window=getattr(self.app,"zone_window",None)
                if window is not None and window.winfo_exists():
                    window.transient("")
                    window.deiconify()
                    window.lift()
                    window.focus_set()
            self.status.set("Eina oberta: "+method)
            return result
        except Exception as exc:
            messagebox.showerror("Error en obrir l'eina",str(exc),parent=self.win)

    def panel(self,parent,title,description,actions):
        outer=tk.Frame(parent,bg=PANEL,padx=18,pady=16)
        outer.pack(fill="x",pady=8)
        label(outer,title,15,CYAN,True).pack(anchor="w")
        label(outer,description,10,MUTED,wraplength=900,justify="left").pack(anchor="w",pady=(5,12))
        buttons=tk.Frame(outer,bg=PANEL);buttons.pack(fill="x")
        for i,(text,fn) in enumerate(actions):
            btn(buttons,text,fn).grid(row=i//4,column=i%4,padx=4,pady=4,sticky="ew")
        for i in range(4):buttons.grid_columnconfigure(i,weight=1)

    def show_section(self,section):
        for child in self.body.winfo_children():child.destroy()
        for name,b in self.nav_buttons.items():
            b.configure(bg=CYAN if name==section else SURFACE,fg="#081a2b" if name==section else TEXT)
        label(self.body,section,20,TEXT,True).pack(anchor="w",pady=(0,6))
        descriptions={
          "Espai":"Quadrícula i zones del motor original. La vista de la graella integrada és una fase posterior.",
          "Targetes":"Les targetes ArUco representen persones, objectes o instruments; conservem l'editor original.",
          "Accions":"Accions per targeta, regles i esdeveniments espacials disponibles al motor.",
          "Música i àudio":"Control MIDI, àudio local, ritmes i volums. La configuració detallada continua a l'editor original.",
          "Visuals":"Previsualització i projecció, amb les eines originals.",
          "Prova":"Càmera, simulador i diagnòstic sense perdre l'accés al sistema existent.",
          "Projectes":"Obre i desa els projectes amb el format original, sense convertir-los."
        }
        if section=="Espai":
            label(self.body,"Quadrícula del mapa espacial actiu · selecció de caselles i zones",10,MUTED).pack(anchor="w",pady=(0,8))
            SpatialGrid(self.body,self).pack(fill="both",expand=True)
            return
        label(self.body,descriptions[section],10,MUTED,wraplength=1000,justify="left").pack(anchor="w",pady=(0,10))
        call=lambda name,*a:lambda:self.invoke(name,*a)
        panels={
          "Espai":[("Zones espacials","Obre l'editor de zones i la quadrícula virtual existent.",[
            ("Editar zones",call("open_zone_editor")),("Càmera ArUco",call("show_panel","camera")),
            ("Calibració",call("open_zone_editor")),("Simulador",call("open_simulator"))])],
          "Targetes":[("Editor i monitor","Configura els 16 marcadors i comprova les targetes actives.",[
            ("Editor de targetes",call("show_panel","editor")),("Targetes en funció",call("show_panel","cards")),
            ("Seguiment",call("open_participants")),("Seguir directe",call("follow_live_preview"))])],
          "Accions":[("Regles i funcions","Accedeix a les regles i a les funcions de cada targeta.",[
            ("Regles i sortides",call("open_rules")),("Editar accions",call("show_panel","editor")),
            ("Zones espacials",call("open_zone_editor")),("Simular",call("open_simulator"))])],
          "Música i àudio":[("Motor musical","Nota MIDI, harmonia, arpegiador, CC, tempo, patrons i bateria.",[
            ("Connexió MIDI",call("show_panel","midi")),("Editor musical",call("show_panel","editor")),
            ("Taula de volums",call("open_mixer")),("Àudio local",call("open_local_audio"))]),
            ("Diagnòstic","Les sortides MIDI continuen gestionades pel motor existent.",[
            ("Diagnosi MIDI",call("open_midi_diagnostics")),("Actualitzar ports",call("refresh_midi"))])],
          "Visuals":[("Imatge i projecció","Manté la previsualització i les finestres de projecció originals.",[
            ("Previsualització",call("show_panel","visual")),("Projecció",call("open_projection")),
            ("Editor de targetes",call("show_panel","editor"))])],
          "Prova":[("Prova en directe","Obre les eines de càmera i simulació del motor original.",[
            ("Càmera",call("show_panel","camera")),("Simulador",call("open_simulator")),
            ("Monitor de targetes",call("show_panel","cards")),("Diagnosi MIDI",call("open_midi_diagnostics"))])],
          "Projectes":[("Gestió de projectes","Desa en el format actual del programa; no es canvia cap esquema.",[
            ("Nou projecte",call("new_project")),("Obrir projecte",call("open_project")),
            ("Desar projecte",call("save_project")),("Desar com...",call("save_project",True))]),
            ("Finestres","Recupera les distribucions de finestres del programa original.",[
            ("Desar distribució",call("save_window_layout")),
            ("Recuperar distribució",call("restore_window_layout")),
            ("Distribució inicial",call("default_window_layout"))])]
        }
        for title,desc,actions in panels[section]:
            self.panel(self.body,title,desc,actions)
        note=tk.Frame(self.body,bg=BG);note.pack(fill="x",pady=(15,0))
        label(note,"Pendent: editor espacial incrustat, Kaoss XY assignable i il·lustracions definitives.",10,MUTED).pack(anchor="w")
        label(note,"Les funcions avançades no es presenten com a implementades.",9,MUTED).pack(anchor="w")

def main():
    splash=tk.Tk();splash.title("ATMO ESFERA FX · Inici")
    splash.geometry("1100x690");splash.minsize(940,620);splash.configure(bg=BG)
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
        btn(options,"Triar una plantilla (projecte existent)",lambda:proceed("template")).pack(fill="x",pady=7)
        btn(options,"Entrar a l'editor sense carregar cap projecte",lambda:proceed(None)).pack(fill="x",pady=7)
        label(splash,"Les plantilles predissenyades encara estan en desenvolupament; de moment pots obrir un projecte com a base.",10,MUTED,wraplength=650).pack(pady=(15,4))
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
