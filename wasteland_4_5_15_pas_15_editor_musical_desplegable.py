import os, sys, json, time, math, random, datetime, threading
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import numpy as np
import cv2
from PIL import Image, ImageTk, ImageDraw, ImageFont
try:
    import mido
except ImportError:
    mido = None

ROOT=Path(__file__).resolve().parent
(ROOT/'PROJECTES').mkdir(exist_ok=True)
(ROOT/'GRAVACIONS').mkdir(exist_ok=True)
W,H=640,360
NAMES=['Motor de ferro','Tempesta de pols','Vapor tòxic','Reactor elèctric','Túnel mecànic','Forja de foc','Fantasma digital','Ones mecàniques','Ferralla orbital','Nucli radioactiu','Ull de la màquina','Sol terminal','Cercle cromàtic 360°']
FUNCS=['Nota MIDI','Harmonia espacial','Arpegiador espacial','Control MIDI CC','Canviar visual','Tempo','Cap acció']
DEFAULTS=[]
for i in range(16):
    DEFAULTS.append({'name':f'Targeta {i+1:02d}','function':'Nota MIDI' if i<4 else ('Control MIDI CC' if i<12 else 'Canviar visual'), 'channel':1,'note':36+i,'cc':20+i,'visual':i%12,'axis':'Rotació','min':0,'max':127,'harmony_key':'La menor','harmony_root':9,'harmony_scale':'Menor natural (eòlica)','harmony_velocity':85,'arp_division':'1/2 temps','arp_gate':60})

NOTE_NAMES=['Do','Do#','Re','Re#','Mi','Fa','Fa#','Sol','Sol#','La','La#','Si']
SCALE_INTERVALS={
 'Major (jònica)':(0,2,4,5,7,9,11),
 'Menor natural (eòlica)':(0,2,3,5,7,8,10),
 'Pentatònica menor':(0,3,5,7,10),
 'Pentatònica major':(0,2,4,7,9),
 'Dòrica':(0,2,3,5,7,9,10),
 'Mixolídia':(0,2,4,5,7,9,10),
 'Menor harmònica':(0,2,3,5,7,8,11),
}
def harmony_pitches(card,sector):
    root=int(card.get('harmony_root',9))%12
    mode=card.get('harmony_scale','Menor natural (eòlica)')
    intervals=SCALE_INTERVALS.get(mode,SCALE_INTERVALS['Menor natural (eòlica)'])
    # Fundamental a l'octava 3, acord derivat de graus de l'escala.
    degree=sector%len(intervals)
    def degree_pitch(index):
      return 48+root+intervals[index%len(intervals)]+12*(index//len(intervals))
    if len(intervals)==5:
      indices=(degree,degree+2,degree+4)
    else:
      indices=(degree,degree+2,degree+4)
    pitches=tuple(max(0,min(127,degree_pitch(j))) for j in indices)
    return pitches,NOTE_NAMES[pitches[0]%12]
class App:
 def __init__(self,root):
    self.root=root; root.title('WASTELAND MACHINE 4.5.15 · Pas 15 · Editor musical desplegable'); root.geometry('790x265'); root.minsize(570,205)
    self.cards=json.loads(json.dumps(DEFAULTS)); self.project='Sense títol'; self.bpm=120
    self.active={}; self.last_seen={}; self.last_cc={}; self.notes={}; self.harmony_notes={}; self.harmony_zones={}; self.harmony_pending={}; self.arp_states={}; self.arp_lock=threading.RLock(); self.arp_stop=threading.Event(); self.current_visual=0
    self.metronome_enabled=False; self.metronome_start=time.monotonic(); self.metronome_last_beat=-1; self.metronome_last_bpm=self.bpm; self.quantize_harmony=tk.BooleanVar(value=True); self.queued_harmony={}; self.clock_next_beat=1; self.clock_last_bpm=self.bpm
    self.camera=None; self.midi=None; self.midi_name=''; self.recording=None; self.record_file=None; self.t0=time.monotonic(); self.last_frame=None; self.visual_paused=False; self.visual_paused_at=None; self.monitor_window=None; self.monitor_table=None; self.monitor_ticks=0
    self.aruco_detector=cv2.aruco.ArucoDetector(cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50))
    self.last_visual_update=0.0; self.visual_interval=1/12; self._closing=False
    yy,xx=np.mgrid[0:H,0:W].astype(np.float32); u=(xx-W/2)/(H/2); v=(yy-H/2)/(H/2)
    self._visual_coords=(u,v,np.sqrt(u*u+v*v)+1e-4,np.arctan2(v,u))
    self.last_color_xy=None; self.smooth_color_xy=None; self.color_smooth_time=None; self.color_transition_seconds=0.5; self.color_max_brightness=0.80; self.card2_rotation_prev=None; self.card2_rotation_total=0.0; self.card2_last_send=0.0; self.card2_cc_values={}; self.card2_volume=0; self.card2_filter=64; self.full=tk.BooleanVar(value=False); self.cam_index=tk.IntVar(value=0)
    self.harmony_key=tk.StringVar(value='La menor'); self.harmony_root=tk.StringVar(value='La'); self.harmony_scale=tk.StringVar(value='Menor natural (eòlica)'); self.bpm_var=tk.IntVar(value=self.bpm); self.harmony_velocity=tk.IntVar(value=85); self.arp_division=tk.StringVar(value='1/2 temps'); self.arp_gate=tk.IntVar(value=60); self.card_id=tk.StringVar(value='01'); self.fun=tk.StringVar(); self.axis=tk.StringVar(); self.note=tk.IntVar(); self.cc=tk.IntVar(); self.channel=tk.IntVar(); self.visual=tk.StringVar(); self.midi_choice=tk.StringVar(value='Sense MIDI'); self.status=tk.StringVar(value='Preparat · Obre la càmera per detectar les targetes')
    self.cards[0]['visual']=12; self.cards[1]['function']='Control MIDI CC'; self.cards[1]['cc']=7; self.cards[1]['axis']='Horitzontal'; self.build(); self.select_visual(12); self.load_card(); self.refresh_midi(); self.root.protocol('WM_DELETE_WINDOW',self.close); self.root.after(50,self.tick); self.root.after(450,self.raise_all_panels); self.arp_thread=threading.Thread(target=self.arpeggio_worker,daemon=True); self.arp_thread.start()
 def build(self):
    bg='#151210'; panel='#261c16'; copper='#ba7945'; cream='#f0d9b5'
    self.root.configure(bg=bg)
    s=ttk.Style(); s.theme_use('clam')
    s.configure('TFrame',background=bg)
    s.configure('TLabel',background=bg,foreground=cream,font=('Segoe UI',9))
    s.configure('TLabelFrame',background=bg,foreground='#f0b36f',bordercolor='#996139',relief='groove',borderwidth=2)
    s.configure('TLabelFrame.Label',background='#2b1e16',foreground='#f2c18c',font=('Segoe UI',10,'bold'))
    s.configure('TButton',background='#65412b',foreground='#fff0d7',padding=(8,5),font=('Segoe UI',9,'bold'),bordercolor='#a36b40',relief='raised')
    s.map('TButton',background=[('active','#95603b'),('pressed','#3d291c')])
    s.configure('Accent.TButton',background='#a95422',foreground='#fff2d9',padding=(9,6))
    s.map('Accent.TButton',background=[('active','#d06b2b')])
    s.configure('TCheckbutton',background=bg,foreground=cream,font=('Segoe UI',9))
    s.configure('TCombobox',fieldbackground='#ebdcc5',background='#90643f')
    s.configure('Treeview',background='#241d18',foreground='#e8d4ba',fieldbackground='#241d18',rowheight=21,font=('Segoe UI',9))
    s.configure('Treeview.Heading',background='#51301e',foreground='#f0ba7b',font=('Segoe UI',9,'bold'))
    menu=tk.Menu(self.root);fm=tk.Menu(menu,tearoff=False)
    fm.add_command(label='Nou projecte',command=self.new_project)
    fm.add_command(label='Obrir projecte...',command=self.open_project)
    fm.add_command(label='Desar projecte',command=self.save_project)
    fm.add_command(label='Desar com...',command=lambda:self.save_project(True))
    fm.add_separator()
    fm.add_command(label='Desar distribució de finestres',command=self.save_window_layout)
    fm.add_command(label='Recuperar distribució desada',command=self.restore_window_layout)
    fm.add_command(label='Restablir distribució inicial',command=self.default_window_layout)
    fm.add_separator();fm.add_command(label='Sortir',command=self.close)
    menu.add_cascade(label='Projecte',menu=fm);self.root.config(menu=menu)
    # Capçalera real extreta del disseny aprovat, no una imitació feta amb text.
    banner=tk.Frame(self.root,bg='#2c1b13',highlightbackground='#9c6139',highlightthickness=2,height=94)
    banner.pack(fill='x',padx=7,pady=(5,3));banner.pack_propagate(False)
    try:
      self.banner_source=Image.open(ROOT/'capcalera_wasteland_4513.png').convert('RGB')
      self.banner_photo=None
      self.banner_label=tk.Label(banner,bg='#20130e',bd=0)
      self.banner_label.pack(fill='both',expand=True)
      self.banner_label.bind('<Configure>',self.resize_banner)
    except Exception:
      tk.Label(banner,text='WASTELAND MACHINE',font=('Georgia',19,'bold'),fg='#f5b47a',bg='#20130e').pack(fill='both',expand=True)
    toolbar=ttk.Frame(self.root);toolbar.pack(fill='x',padx=9,pady=(1,5))
    ttk.Button(toolbar,text='MONITOR ARUCO',command=self.open_aruco_monitor).pack(side='left',padx=2)
    ttk.Button(toolbar,text='MOSTRAR TOTES LES FINESTRES',command=self.show_all_panels).pack(side='left',padx=7)
    ttk.Label(toolbar,text='v 4.5.15 · Pas 15',foreground='#d5a16b').pack(side='right',padx=7)
    # Cada mòdul té una finestra nativa de Windows: es pot arrossegar,
    # canviar de mida, minimitzar i restaurar independentment.
    self.panel_windows={}
    self.window_layout_file=ROOT/'PROJECTES'/'distribucio_finestres.json'
    self.camera_window=self.make_panel_window('camera','CÀMERA ARUCO', '680x460+35+300')
    camera_controls=ttk.Frame(self.camera_window);camera_controls.pack(fill='x',padx=5,pady=(5,0))
    ttk.Button(camera_controls,text='OBRIR / TANCAR CÀMERA',command=self.toggle_cam).pack(side='left',padx=3)
    self.cam_label=tk.Label(self.camera_window,bg='#0c1012',fg='#e0c3a0',text='Càmera desconnectada',anchor='center',bd=0)
    self.cam_label.pack(fill='both',expand=True,padx=5,pady=5)
    self.visual_window=self.make_panel_window('visual','VISUAL · PREVISUALITZACIÓ','680x460+740+300')
    self.vis_label=tk.Label(self.visual_window,bg='#0d0b0b',fg='#e0c3a0',anchor='center',bd=0)
    self.vis_label.pack(fill='both',expand=True,padx=5,pady=5)
    self.midi_window=self.make_panel_window('midi','CONNEXIÓ MIDI → CAKEWALK','315x210+815+65')
    midi_box=ttk.Frame(self.midi_window);midi_box.pack(fill='both',expand=True,padx=6,pady=6)
    self.editor_window=self.make_panel_window('editor','EDITOR DE TARGETES','350x650+1430+80')
    right_outer=ttk.Frame(self.editor_window);right_outer.pack(fill='both',expand=True)
    sidebar=tk.Canvas(right_outer,bg=bg,highlightthickness=0)
    sidebar_scroll=ttk.Scrollbar(right_outer,orient='vertical',command=sidebar.yview)
    sidebar_scroll.pack(side='right',fill='y');sidebar.pack(side='left',fill='both',expand=True)
    sidebar.configure(yscrollcommand=sidebar_scroll.set)
    right=ttk.Frame(sidebar)
    sidebar_window=sidebar.create_window((0,0),window=right,anchor='nw')
    right.bind('<Configure>',lambda e:sidebar.configure(scrollregion=sidebar.bbox('all')))
    sidebar.bind('<Configure>',lambda e:sidebar.itemconfigure(sidebar_window,width=e.width))
    def wheel(event):sidebar.yview_scroll(-1 if event.delta>0 else 1,'units')
    sidebar.bind('<MouseWheel>',wheel);right.bind('<MouseWheel>',wheel)
    frame=self.sidebar_panel(right,'EDITOR DE TARGETES',pady=3)
    control_strip=tk.Frame(self.root,bg='#1e1712',highlightbackground='#6e452e',highlightthickness=1)
    control_strip.pack(fill='x',padx=8,pady=(2,4))
    ttk.Button(control_strip,text='CÀMERA',command=lambda:self.toggle_panel('camera')).pack(side='left',padx=3,pady=3)
    ttk.Button(control_strip,text='VISUAL',command=lambda:self.toggle_panel('visual')).pack(side='left',padx=3)
    ttk.Button(control_strip,text='MIDI',command=lambda:self.toggle_panel('midi')).pack(side='left',padx=3)
    ttk.Button(control_strip,text='EDITOR',command=lambda:self.toggle_panel('editor')).pack(side='left',padx=3)
    ttk.Button(control_strip,text='PROJECCIÓ',command=self.open_projection,style='Accent.TButton').pack(side='left',padx=3)
    ttk.Label(control_strip,text='BPM').pack(side='left',padx=(8,2))
    bpm_spin=tk.Spinbox(control_strip,textvariable=self.bpm_var,from_=40,to=180,increment=1,width=5,command=self.update_bpm,bg='#e9d8c2')
    bpm_spin.pack(side='left',padx=3)
    bpm_spin.bind('<Return>',lambda event:self.update_bpm())
    bpm_spin.bind('<FocusOut>',lambda event:self.update_bpm())
    ttk.Button(control_strip,text='APLICAR BPM',command=self.update_bpm).pack(side='left',padx=3)
    self.metronome_button=ttk.Button(control_strip,text='METRÒNOM: OFF',command=self.toggle_metronome)
    self.metronome_button.pack(side='left',padx=(9,3))
    self.beat_light=tk.Label(control_strip,text='●',bg='#1e1712',fg='#55483e',font=('Segoe UI',17,'bold'))
    self.beat_light.pack(side='left',padx=(1,5))
    ttk.Checkbutton(control_strip,text='ACORDS AL TEMPS',variable=self.quantize_harmony,command=self.toggle_quantization).pack(side='left',padx=(2,5))
    self.midi_cb=ttk.Combobox(midi_box,textvariable=self.midi_choice,width=26,state='readonly');self.midi_cb.pack(fill='x',padx=7,pady=(7,3))
    ttk.Button(midi_box,text='ACTUALITZAR PORTS',command=self.refresh_midi).pack(fill='x',padx=7,pady=2)
    ttk.Button(midi_box,text='CONNECTAR / FIXAR MIDI',command=self.connect_midi,style='Accent.TButton').pack(fill='x',padx=7,pady=3)
    self.midi_indicator=ttk.Label(midi_box,text='Estat: desconnectat',foreground='#7de0ac')
    self.midi_indicator.pack(fill='x',padx=7,pady=(1,6))
    self.midi_cb.bind('<<ComboboxSelected>>',lambda e:self.connect_midi())
    ttk.Label(frame,text='Targeta / ID ArUco').pack(anchor='w',padx=8,pady=(5,0))
    cb=ttk.Combobox(frame,textvariable=self.card_id,values=[f'{i+1:02d}' for i in range(16)],state='readonly',width=24)
    cb.pack(padx=8,fill='x');cb.bind('<<ComboboxSelected>>',lambda e:self.load_card())
    for label,var,vals in [('Funció',self.fun,FUNCS),('Moviment que controla el valor',self.axis,['Rotació','Horitzontal','Vertical'])]:
      ttk.Label(frame,text=label).pack(anchor='w',padx=8,pady=(5,0))
      combo=ttk.Combobox(frame,textvariable=var,values=vals,state='readonly',width=25)
      combo.pack(fill='x',padx=8)
      if label=='Funció':combo.bind('<<ComboboxSelected>>',self.on_function_selected)
    for label,var,from_,to in [('Canal MIDI (1-16)',self.channel,1,16),('Nota MIDI (0-127)',self.note,0,127),('Control CC (0-127)',self.cc,0,127)]:
      ttk.Label(frame,text=label).pack(anchor='w',padx=8,pady=(5,0))
      tk.Spinbox(frame,textvariable=var,from_=from_,to=to,width=8,bg='#e9d8c2').pack(anchor='w',padx=8)
    ttk.Button(frame,text='CONFIGURAR HARMONIA / ARPEGIADOR…',command=self.open_music_settings).pack(fill='x',padx=8,pady=(9,4))
    ttk.Label(frame,text='Les escales, la força i el ritme són dins la finestra de configuració musical.',wraplength=245,foreground='#c9aa83').pack(anchor='w',padx=8,pady=(0,5))
    ttk.Label(frame,text='Visual assignat').pack(anchor='w',padx=8,pady=(5,0))
    ttk.Combobox(frame,textvariable=self.visual,values=NAMES,state='readonly',width=25).pack(fill='x',padx=8)
    ttk.Button(frame,text='APLICAR / CREAR TARGETA',command=self.apply_card,style='Accent.TButton').pack(fill='x',padx=8,pady=9)
    statusbar=tk.Frame(self.root,bg='#1a1714',highlightbackground='#6f472f',highlightthickness=1)
    statusbar.pack(fill='x',padx=8,pady=(1,4))
    tk.Label(statusbar,text='●',bg='#1a1714',fg='#42c990').pack(side='left',padx=(6,2))
    ttk.Label(statusbar,textvariable=self.status,foreground='#e8b47d').pack(side='left',padx=4)
 def make_panel_window(self,key,title,geometry):
    win=tk.Toplevel(self.root)
    win.title('WASTELAND · '+title)
    # Finestra propietat de la principal: Windows la manté al davant
    # de la principal, però no per sobre de Cakewalk.
    win.transient(self.root)
    win.geometry(geometry)
    win.minsize(250,140)
    win.configure(bg='#151210')
    win.protocol('WM_DELETE_WINDOW',win.withdraw)
    self.panel_windows[key]=win
    # Finestres germanes de la principal, no modals: totes poden estar obertes alhora.
    # No fem servir grab_set ni focus_force, que impedirien treballar amb Cakewalk.
    return win
 def toggle_panel(self,key):
    win=self.panel_windows.get(key)
    if not win or not win.winfo_exists():return
    # Tancar = amagar el panell, mai aturar càmera ni desconnectar MIDI.
    if win.state()=='withdrawn':self.show_panel(key)
    else:win.withdraw()
 def toggle_quantization(self):
    # Quan es desactiva la quantització, els canvis pendents entren immediatament.
    if not self.quantize_harmony.get():
      for i,zone in list(self.queued_harmony.items()):
        if i in self.active:self.play_harmony_zone(i,zone)
      self.queued_harmony.clear()
    self.status.set('Acords al temps: '+('ACTIVAT' if self.quantize_harmony.get() else 'DESACTIVAT'))
 def musical_clock_tick(self):
    now=time.monotonic()
    if self.clock_last_bpm!=self.bpm:
      self.clock_last_bpm=self.bpm
      self.metronome_start=now
      self.clock_next_beat=1
      self.metronome_last_beat=-1
    interval=60.0/max(1,self.bpm)
    current=int((now-self.metronome_start)/interval)
    if current>=self.clock_next_beat:
      # No reproduïm pulsacions acumulades després d'una aturada de la GUI.
      self.clock_next_beat=current+1
      if self.quantize_harmony.get():
        for i,zone in list(self.queued_harmony.items()):
          if i in self.active:self.play_harmony_zone(i,zone)
        self.queued_harmony.clear()
 def toggle_metronome(self):
    self.metronome_enabled=not self.metronome_enabled
    self.metronome_last_beat=-1
    self.metronome_last_bpm=self.bpm
    self.metronome_button.config(text='METRÒNOM: ON' if self.metronome_enabled else 'METRÒNOM: OFF')
    if not self.metronome_enabled:self.beat_light.config(fg='#55483e')
 def update_metronome_light(self):
    if not self.metronome_enabled:return
    now=time.monotonic()
    if self.metronome_last_bpm!=self.bpm:
      self.metronome_last_bpm=self.bpm
      self.metronome_last_beat=-1
    interval=60.0/max(1,self.bpm)
    elapsed=now-self.metronome_start
    beat=int(elapsed/interval)
    phase=(elapsed/interval)-beat
    if beat!=self.metronome_last_beat:self.metronome_last_beat=beat
    if phase<0.17:
      self.beat_light.config(fg='#ffb44b' if beat%4==0 else '#5ff0ac')
    else:self.beat_light.config(fg='#55483e')
 def show_panel(self,key):
    win=self.panel_windows.get(key)
    if win and win.winfo_exists():
      win.deiconify()
      win.lift()
 def show_all_panels(self):
    for key in self.panel_windows:self.show_panel(key)
 def default_window_layout(self):
    # Pantalla principal maximitzada; els quatre mòduls ocupen una quadrícula
    # sense superposar-se, amb marges adaptats a la resolució de Windows.
    try:self.root.state('zoomed')
    except tk.TclError:
      self.root.geometry(f'{self.root.winfo_screenwidth()}x{self.root.winfo_screenheight()}+0+0')
    self.root.update_idletasks()
    sw=self.root.winfo_screenwidth();sh=self.root.winfo_screenheight()
    # Deixem la barra de tasques i un marge superior per als controls principals.
    margin=12;top=max(175,min(245,int(sh*.24)))
    usable_w=max(650,sw-3*margin)
    left=max(300,int(usable_w*.53));right=max(300,usable_w-left)
    usable_h=max(330,sh-top-2*margin-48)
    upper=max(165,int(usable_h*.60));lower=max(145,usable_h-upper)
    layouts={
      'camera':(margin,top,left,upper),
      'visual':(margin*2+left,top,right,upper),
      'midi':(margin,top+upper+margin,left,lower),
      'editor':(margin*2+left,top+upper+margin,right,lower),
    }
    for key,(x,y,w,h) in layouts.items():
      win=self.panel_windows.get(key)
      if win and win.winfo_exists():
        win.deiconify()
        win.geometry(f'{w}x{h}+{x}+{y}')
        win.lift(self.root)
    self.status.set('Finestres ordenades. Mou-les o desa la teva distribució des de Projecte.')
 def raise_all_panels(self):
    # La distribució inicial serveix de base si no hi ha cap desat o és incomplet.
    self.default_window_layout()
    if self.window_layout_file.exists():self.restore_window_layout()
 def save_window_layout(self):
    layout={'main':self.root.geometry(),'panels':{}}
    for key,win in self.panel_windows.items():
      if not win.winfo_exists():continue
      state=win.state()
      layout['panels'][key]={'geometry':win.geometry(),
                             'visible':state not in ('withdrawn','iconic')}
    try:
      with open(self.window_layout_file,'w',encoding='utf-8') as f:
        json.dump(layout,f,ensure_ascii=False,indent=2)
      self.status.set('Distribució de finestres desada. Es recuperarà en tornar a obrir Wasteland.')
    except Exception as exc:self.status.set('No s’ha pogut desar la distribució: '+str(exc))
 def restore_window_layout(self,silent=False):
    if not self.window_layout_file.exists():
      if not silent:self.status.set('Encara no hi ha cap distribució de finestres desada.')
      return
    try:
      with open(self.window_layout_file,encoding='utf-8') as f:layout=json.load(f)
      if 'main' in layout:self.root.geometry(layout['main'])
      for key,data in layout.get('panels',{}).items():
        win=self.panel_windows.get(key)
        if not win or not win.winfo_exists():continue
        if 'geometry' in data:win.geometry(data['geometry'])
        if data.get('visible',True):
          win.deiconify()
          win.lift(self.root)
        else:win.withdraw()
      if not silent:self.status.set('Distribució de finestres recuperada.')
    except Exception as exc:
      self.status.set('No s’ha pogut recuperar la distribució: '+str(exc))
 def resize_banner(self,event):
    if event.width<10 or event.height<10:return
    im=self.banner_source
    # Omplim tota la capçalera sense deformar-la.
    scale=max(event.width/im.width,event.height/im.height)
    nw=max(1,int(im.width*scale));nh=max(1,int(im.height*scale))
    resized=im.resize((nw,nh),Image.Resampling.LANCZOS)
    x=(nw-event.width)//2;y=(nh-event.height)//2
    self.banner_photo=ImageTk.PhotoImage(resized.crop((x,y,x+event.width,y+event.height)))
    self.banner_label.config(image=self.banner_photo)
 def sidebar_panel(self,parent,title,pady=3):
    # Marc de ferro rovellat, capçalera de coure i reblons decoratius.
    outer=tk.Frame(parent,bg='#241711',highlightbackground='#b77943',highlightthickness=2,bd=2,relief='ridge')
    outer.pack(fill='x',pady=pady,padx=2)
    header=tk.Frame(outer,bg='#493020',height=29)
    header.pack(fill='x');header.pack_propagate(False)
    tk.Label(header,text='●',bg='#493020',fg='#e3a36b',font=('Segoe UI',9,'bold')).pack(side='left',padx=(5,4))
    tk.Label(header,text=title,bg='#493020',fg='#ffcf92',font=('Segoe UI',9,'bold')).pack(side='left')
    tk.Label(header,text='●',bg='#493020',fg='#e3a36b',font=('Segoe UI',9,'bold')).pack(side='right',padx=5)
    body=tk.Frame(outer,bg='#2c2019',padx=3,pady=5)
    body.pack(fill='both',expand=True,padx=3,pady=(0,3))
    return body
 def industrial_panel(self,parent,title,row,col,padx):
    shell=tk.Frame(parent,bg='#3b281c',highlightbackground='#b67a45',highlightthickness=2)
    shell.grid(row=row,column=col,sticky='nsew',padx=padx)
    header=tk.Frame(shell,bg='#39251b',height=29)
    header.pack(fill='x');header.pack_propagate(False)
    tk.Label(header,text='◉',bg='#39251b',fg='#c38a52',font=('Segoe UI',10,'bold')).pack(side='left',padx=(4,3))
    tk.Label(header,text=title,bg='#39251b',fg='#f3c28b',font=('Segoe UI',10,'bold')).pack(side='left')
    tk.Label(header,text='◉',bg='#39251b',fg='#c38a52',font=('Segoe UI',10,'bold')).pack(side='right',padx=5)
    return shell
 def choose_card_from_table(self,event=None):
    sel=self.cards_table.selection()
    if not sel:return
    self.card_id.set(f'{int(sel[0])+1:02d}')
    self.load_card()
 def update_cards_table(self):
    if not hasattr(self,'cards_table'):return
    for i,c in enumerate(self.cards):
      val=(f'{i+1:02d}',c.get('name',f'Targeta {i+1:02d}'),c['function'],c['channel'],c['note'] if c['function']=='Nota MIDI' else c['cc'],NAMES[c['visual']] if c['function']=='Canviar visual' else '—',c['axis'])
      iid=str(i);tag='active' if i in self.active else ('odd' if i%2 else 'even')
      if self.cards_table.exists(iid):self.cards_table.item(iid,values=val,tags=(tag,))
      else:self.cards_table.insert('', 'end',iid=iid,values=val,tags=(tag,))
 def make_banner(self):
    # Dibuix vectorial propi, sense fitxers d'imatge externs.
    im=Image.new('RGB',(174,68),'#302820'); d=ImageDraw.Draw(im)
    d.rectangle((0,0,173,67),outline='#9c764b',width=2)
    # Terra i cúpula geodèsica triangular.
    d.line((8,56,166,56),fill='#bd8d57',width=2)
    import math as _m
    cx,cy,r=78,56,42
    pts=[(cx+int(r*_m.cos(_m.pi+(i/24)*_m.pi)),cy+int(r*_m.sin(_m.pi+(i/24)*_m.pi))) for i in range(25)]
    d.line(pts,fill='#e4b776',width=2)
    for xx in (50,65,80,95,110):
      yy=cy-int(_m.sqrt(max(0,r*r-(xx-cx)**2)))
      d.line((xx,yy,xx,56),fill='#9e805b',width=1)
    for yy in (33,44):
      span=int(_m.sqrt(max(0,r*r-(cy-yy)**2)))
      d.line((cx-span,yy,cx+span,yy),fill='#9e805b',width=1)
    d.line((38,56,65,33,92,44,118,56),fill='#d2a36d',width=1)
    d.line((38,56,65,44,92,33,118,56),fill='#d2a36d',width=1)
    # Ovni i petit robot mecànic.
    d.ellipse((126,13,164,25),fill='#b68a56',outline='#f5cf91',width=2)
    d.arc((136,7,155,23),180,360,fill='#e7bf7d',width=2)
    d.ellipse((141,17,147,21),fill='#7ce4d0')
    d.ellipse((15,28,37,50),fill='#bd8b58',outline='#f2c58b',width=2)
    d.ellipse((19,35,25,41),fill='#f4d08d');d.ellipse((29,35,35,41),fill='#f4d08d')
    d.line((26,28,26,21),fill='#e1b778',width=2);d.ellipse((24,18,28,22),fill='#f5c47a')
    return ImageTk.PhotoImage(im)
 def open_aruco_monitor(self):
    if self.monitor_window is not None and self.monitor_window.winfo_exists():
      self.monitor_window.lift(); self.monitor_window.focus_force(); return
    win=tk.Toplevel(self.root)
    win.title('MONITOR ARUCO · Valors en directe')
    win.geometry('1120x570'); win.minsize(850,400); win.configure(bg='#161a1e')
    self.monitor_window=win
    ttk.Label(win,text='16 TARGETES · CONFIGURACIO I LECTURA EN DIRECTE',font=('Segoe UI',13,'bold'),foreground='#ffae58').pack(anchor='w',padx=12,pady=(12,4))
    ttk.Label(win,text='ID ArUco: 0-15  |  Targeta: 01-16  |  Posicio: percentatge  |  Rotacio: graus  |  Valor: 0-127').pack(anchor='w',padx=12,pady=(0,8))
    holder=ttk.Frame(win); holder.pack(fill='both',expand=True,padx=12,pady=4)
    cols=('targeta','id','estat','funcio','canal','nota','cc','eix','valor','x','y','angle','visual')
    headings=('Targeta','ID','Estat','Funcio','Canal','Nota','CC','Eix','Valor','X %','Y %','Graus','Visual')
    widths=(68,42,85,135,55,55,45,95,65,60,60,65,155)
    tree=ttk.Treeview(holder,columns=cols,show='headings',height=16)
    for col,title,width in zip(cols,headings,widths):
      tree.heading(col,text=title); tree.column(col,width=width,minwidth=40,anchor='center',stretch=(col in ('funcio','visual')))
    tree.tag_configure('on',background='#29453d',foreground='#ffffff')
    tree.tag_configure('off',background='#22272b',foreground='#b9c0c4')
    scroll=ttk.Scrollbar(holder,orient='vertical',command=tree.yview)
    tree.configure(yscrollcommand=scroll.set)
    scroll.pack(side='right',fill='y');tree.pack(side='left',fill='both',expand=True)
    self.monitor_table=tree
    self.update_aruco_monitor()
    ttk.Label(win,text='Els valors en directe nomes apareixen quan el marcador es detecta. Els canvis de configuracio es veuen despres de prémer APLICAR A LA TARGETA.').pack(anchor='w',padx=12,pady=(5,12))
    def on_close():
      self.monitor_table=None;self.monitor_window=None;win.destroy()
    win.protocol('WM_DELETE_WINDOW',on_close)
 def update_aruco_monitor(self):
    tree=self.monitor_table
    if tree is None or not tree.winfo_exists():return
    for i,c in enumerate(self.cards):
      active=i in self.active
      x,y,a=self.active[i] if active else (None,None,None)
      axis_value={'Rotació':a,'Horitzontal':x,'Vertical':y}.get(c['axis'],a) if active else None
      val=round(max(0,min(1,axis_value))*127) if axis_value is not None else '--'
      values=(f'{i+1:02d}',i,'ACTIU' if active else 'Inactiu',c['function'],c['channel'],c['note'],c['cc'],c['axis'],val,
              f'{x*100:.1f}' if active else '--',f'{y*100:.1f}' if active else '--',f'{a*360:.1f}' if active else '--',NAMES[c['visual']])
      iid=str(i)
      if tree.exists(iid):tree.item(iid,values=values,tags=('on' if active else 'off',))
      else:tree.insert('', 'end',iid=iid,values=values,tags=('on' if active else 'off',))
 def on_function_selected(self,event=None):
    if self.fun.get() in ('Harmonia espacial','Arpegiador espacial'):
      self.open_music_settings()
 def open_music_settings(self):
    kind=self.fun.get()
    if kind not in ('Harmonia espacial','Arpegiador espacial'):
      messagebox.showinfo('Configuració musical','Selecciona Harmonia espacial o Arpegiador espacial a la funció de la targeta.',parent=self.editor_window)
      return
    old=getattr(self,'music_settings_window',None)
    if old is not None and old.winfo_exists():
      old.destroy()
    win=tk.Toplevel(self.root)
    self.music_settings_window=win
    win.title('WASTELAND · '+kind.upper()+' · TARGETA '+self.card_id.get())
    win.geometry('370x425' if kind=='Arpegiador espacial' else '370x315')
    win.minsize(320,275)
    win.configure(bg='#151210')
    win.transient(self.root)
    win.lift(self.root)
    pane=ttk.Frame(win);pane.pack(fill='both',expand=True,padx=16,pady=12)
    ttk.Label(pane,text=kind.upper(),foreground='#e7ae70',font=('Segoe UI',12,'bold')).pack(anchor='w',pady=(0,12))
    ttk.Label(pane,text='Nota fonamental').pack(anchor='w',pady=(4,2))
    ttk.Combobox(pane,textvariable=self.harmony_root,values=NOTE_NAMES,state='readonly').pack(fill='x')
    ttk.Label(pane,text='Escala / mode').pack(anchor='w',pady=(9,2))
    ttk.Combobox(pane,textvariable=self.harmony_scale,values=list(SCALE_INTERVALS),state='readonly').pack(fill='x')
    ttk.Label(pane,text='Força de les notes MIDI (1–127)').pack(anchor='w',pady=(9,2))
    tk.Spinbox(pane,textvariable=self.harmony_velocity,from_=1,to=127,bg='#e9d8c2').pack(anchor='w')
    if kind=='Arpegiador espacial':
      ttk.Label(pane,text='Divisió rítmica').pack(anchor='w',pady=(10,2))
      ttk.Combobox(pane,textvariable=self.arp_division,values=['1 temps','1/2 temps','1/4 temps'],state='readonly').pack(fill='x')
      ttk.Label(pane,text='Durada de les notes (%)').pack(anchor='w',pady=(10,2))
      tk.Spinbox(pane,textvariable=self.arp_gate,from_=10,to=95,increment=5,bg='#e9d8c2').pack(anchor='w')
    ttk.Button(pane,text='APLICAR A LA TARGETA I TANCAR',command=lambda:(self.apply_card(),win.destroy())).pack(fill='x',pady=(16,4))
    ttk.Label(pane,text='Per conservar els canvis en disc: Projecte → Desar projecte.',wraplength=320).pack(anchor='w',pady=(5,0))
 def load_card(self):
    c=self.cards[int(self.card_id.get())-1]; self.fun.set(c['function']); self.axis.set(c['axis']); self.note.set(c['note']); self.cc.set(c['cc']); self.channel.set(c['channel']); self.visual.set(NAMES[c['visual']]); self.harmony_key.set(c.get('harmony_key','La menor')); self.harmony_root.set(NOTE_NAMES[int(c.get('harmony_root',9))%12]); self.harmony_scale.set(c.get('harmony_scale','Menor natural (eòlica)')); self.harmony_velocity.set(c.get('harmony_velocity',85)); self.arp_division.set(c.get('arp_division','1/2 temps')); self.arp_gate.set(c.get('arp_gate',60))
 def apply_card(self):
    try:
      card_index=int(self.card_id.get())-1
      self.stop_harmony(card_index)
      c=self.cards[card_index]; c.update(arp_division=self.arp_division.get(),arp_gate=max(10,min(95,int(self.arp_gate.get()))),harmony_root=NOTE_NAMES.index(self.harmony_root.get()),harmony_scale=self.harmony_scale.get(),harmony_velocity=max(1,min(127,int(self.harmony_velocity.get()))),function=self.fun.get(),axis=self.axis.get(),note=max(0,min(127,int(self.note.get()))),cc=max(0,min(127,int(self.cc.get()))),channel=max(1,min(16,int(self.channel.get()))),visual=NAMES.index(self.visual.get()))
      if c['visual']==12 and int(self.card_id.get())-1 in self.active:self.select_visual(12)
      self.status.set(f'Targeta {self.card_id.get()} configurada. Desa el projecte per conservar els canvis.');self.update_cards_table()
    except Exception as e: messagebox.showerror('Configuració',str(e))
 def new_project(self):
    self.all_notes_off(); self.cards=json.loads(json.dumps(DEFAULTS)); self.cards[0]['visual']=12; self.cards[1].update(function='Control MIDI CC',cc=7,axis='Horitzontal'); self.project='Sense títol'; self.load_card();self.update_cards_table(); self.status.set('Projecte nou')
 def update_bpm(self):
    try:
      with self.arp_lock:
        self.bpm=max(40,min(180,int(self.bpm_var.get())))
        self.metronome_start=time.monotonic()
        self.clock_last_bpm=self.bpm
        self.metronome_last_bpm=self.bpm
        self.clock_next_beat=1
      self.bpm_var.set(self.bpm)
      self.status.set(f'Rellotge musical: {self.bpm} BPM. Acords quantitzats si activats; Cakewalk conserva el seu tempo.')
    except (ValueError,tk.TclError):self.status.set('Tempo no vàlid')
 def save_project(self,as_new=False):
    self.apply_card()
    if as_new or self.project=='Sense títol':
      path=filedialog.asksaveasfilename(initialdir=ROOT/'PROJECTES',defaultextension='.json',filetypes=[('Projecte Wasteland','*.json')])
      if not path:return
      self.project=path
    try:
      with open(self.project,'w',encoding='utf-8') as f:json.dump({'version':4,'cards':self.cards,'bpm':self.bpm,'quantize_harmony':self.quantize_harmony.get(),'visual':self.current_visual},f,ensure_ascii=False,indent=2)
      self.status.set(f'Projecte desat: {Path(self.project).name}')
    except Exception as e:messagebox.showerror('Desar',str(e))
 def open_project(self):
    path=filedialog.askopenfilename(initialdir=ROOT/'PROJECTES',filetypes=[('Projecte Wasteland','*.json')]);
    if not path:return
    try:
      with open(path,encoding='utf-8') as f:d=json.load(f)
      if len(d['cards'])!=16:raise ValueError('El projecte no conté 16 targetes')
      self.all_notes_off(); self.cards=d['cards']; self.bpm=d.get('bpm',120); self.bpm_var.set(self.bpm); self.quantize_harmony.set(d.get('quantize_harmony',True)); self.select_visual(int(d.get('visual',0))%len(NAMES)); self.project=path; self.load_card();self.update_cards_table(); self.status.set('Projecte obert: '+Path(path).name)
    except Exception as e:messagebox.showerror('Obrir',str(e))
 def refresh_midi(self):
     # No amaguem els errors: aixi podem diagnosticar loopMIDI.
     if mido is None:
       self.midi_cb['values']=['Sense MIDI']
       self.midi_choice.set('Sense MIDI')
       self.status.set('MIDI no disponible: el modul mido no es pot importar. Python: '+sys.executable)
       messagebox.showwarning('Diagnosi MIDI', 'No es pot importar mido.\nPython utilitzat: '+sys.executable)
       return
     try:
       ports=mido.get_output_names()
     except Exception as first_error:
       try:
         mido.set_backend('mido.backends.rtmidi')
         ports=mido.get_output_names()
       except Exception as second_error:
         self.midi_cb['values']=['Sense MIDI']
         self.midi_choice.set('Sense MIDI')
         detail=('No es poden llegir els ports MIDI.\n\n'
                 +'Primer error: '+str(first_error)+'\n'
                 +'Segon error: '+str(second_error)+'\n\n'
                 +'Python: '+sys.executable)
         self.status.set('Error de deteccio MIDI: '+str(second_error))
         messagebox.showerror('Diagnosi MIDI',detail)
         return
     self.midi_cb['values']=['Sense MIDI']+ports
     if self.midi_choice.get() not in self.midi_cb['values']:
       self.midi_choice.set('Sense MIDI')
     if ports:
       self.status.set('Ports MIDI detectats: '+', '.join(ports))
     else:
       self.status.set('No hi ha ports MIDI disponibles. Python: '+sys.executable)
 def connect_midi(self):
    self.all_notes_off()
    if self.midi:
      try:self.midi.close()
      except Exception:pass
    self.midi=None; self.card2_cc_values.clear(); name=self.midi_choice.get()
    if name=='Sense MIDI':
      self.status.set('MIDI desconnectat');self.midi_indicator.config(text='Estat: desconnectat');return
    try:
      self.midi=mido.open_output(name);self.status.set('MIDI connectat a '+name)
      self.midi_indicator.config(text='CONNECTAT: '+name)
    except Exception as e:
      self.midi_indicator.config(text='ERROR DE CONNEXIÓ');messagebox.showerror('MIDI',str(e))
 def toggle_cam(self):
    if self.camera:
      self.camera.release();self.camera=None
      for i in list(self.active):self.deactivate(i)
      self.all_notes_off()
      self.cam_label.config(image='',text='Càmera desconnectada')
      self.status.set('Càmera tancada');return
    backend=cv2.CAP_DSHOW if sys.platform=='win32' else cv2.CAP_ANY
    self.camera=cv2.VideoCapture(self.cam_index.get(),backend)
    if not self.camera.isOpened():
      self.camera.release();self.camera=None;messagebox.showwarning('Càmera','No es pot obrir la webcam. Tanca altres programes que la utilitzin.');return
    self.camera.set(cv2.CAP_PROP_FRAME_WIDTH,640);self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT,480)
    self.status.set('Càmera connectada')
 def select_visual(self,i):
    self.current_visual=i%len(NAMES)
 def toggle_visual_pause(self):
     if not self.visual_paused:
       self.visual_paused=True; self.visual_paused_at=time.monotonic()
       self.pause_button.config(text='REPRENDRE VISUALS')
       self.status.set('Visuals en pausa · Càmera i MIDI continuen actius')
     else:
       self.visual_paused=False
       if self.visual_paused_at is not None:self.t0+=time.monotonic()-self.visual_paused_at
       self.visual_paused_at=None
       self.pause_button.config(text='PAUSAR VISUALS')
       self.status.set('Visuals en marxa')
 def open_projection(self):
    if getattr(self,'projection',None) and self.projection.winfo_exists():
      self.projection.lift();return
    self.projection=tk.Toplevel(self.root);self.projection.title('PROJECCIÓ · COLOR PLA · WASTELAND MACHINE');self.projection.geometry('960x540');self.projection.configure(bg='black')
    self.proj_label=tk.Label(self.projection,bg='black');self.proj_label.pack(fill='both',expand=True)
    self.projection.bind('<F11>',lambda e:self.projection.attributes('-fullscreen',not self.projection.attributes('-fullscreen')))
    self.projection.bind('<Escape>',lambda e:self.projection.attributes('-fullscreen',False))
    self.projection.protocol('WM_DELETE_WINDOW',self.projection.destroy)
 def toggle_record(self):
    if self.recording:
      self.recording.release();self.recording=None;self.rec_label.config(text='● REC OFF');self.status.set('Vídeo guardat: '+str(self.record_file));return
    path=ROOT/'GRAVACIONS'/('visual_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S')+'.avi')
    wr=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'MJPG'),20,(W,H))
    if not wr.isOpened():messagebox.showerror('Gravació','No es pot crear el vídeo AVI');return
    self.recording=wr;self.record_file=path;self.rec_label.config(text='● GRAVANT',foreground='red');self.status.set('Gravant visuals a '+str(path))
 def all_notes_off(self):
    if self.midi:
      for (ch,note) in list(self.notes.values()):
        try:self.midi.send(mido.Message('note_off',channel=ch,note=note,velocity=0))
        except Exception:pass
    self.notes.clear(); self.queued_harmony.clear()
    for i in list(self.arp_states):self.stop_arpeggio(i)
    for i in list(self.harmony_notes):self.stop_harmony(i)
 def stop_arpeggio(self,i):
    with self.arp_lock:
      state=self.arp_states.pop(i,None)
      if state and state.get('playing') and self.midi:
        ch,note=state['playing']
        try:self.midi.send(mido.Message('note_off',channel=ch,note=note,velocity=0))
        except Exception:pass
 def arpeggio_worker(self):
    # Rellotge MIDI independent del dibuix i de la lectura de la càmera.
    # Fem servir temps absolut: no acumulem retards d'un cicle a l'altre.
    while not self.arp_stop.wait(.003):
      with self.arp_lock:
        if self._closing:break
        now=time.monotonic()
        for i,state in list(self.arp_states.items()):
          if state.get('playing') and now>=state.get('off_at',0):
            ch,note=state['playing']
            if self.midi:
              try:self.midi.send(mido.Message('note_off',channel=ch,note=note,velocity=0))
              except Exception:pass
            state['playing']=None
          c=self.cards[i]
          division={'1 temps':1,'1/2 temps':2,'1/4 temps':4}.get(c.get('arp_division','1/2 temps'),2)
          interval=60.0/max(1,self.bpm)/division
          step=math.floor((now-self.metronome_start)/interval)
          if step<0 or step==state.get('last_step'):continue
          state['last_step']=step
          if state.get('playing'):
            ch,note=state['playing']
            if self.midi:
              try:self.midi.send(mido.Message('note_off',channel=ch,note=note,velocity=0))
              except Exception:pass
            state['playing']=None
          notes=state['pitches']
          if not notes:continue
          note=notes[state['index']%len(notes)]
          state['index']+=1
          ch=max(0,min(15,int(c['channel'])-1))
          if self.midi:
            try:
              self.midi.send(mido.Message('note_on',channel=ch,note=note,velocity=max(1,min(127,int(c.get('harmony_velocity',85))))))
              state['playing']=(ch,note)
              # La durada també es calcula des de la graella absoluta.
              state['off_at']=self.metronome_start+(step+max(.1,min(.95,int(c.get('arp_gate',60))/100)))*interval
            except Exception:pass
 def spatial_arpeggio(self,i,x,y):
    c=self.cards[i]
    dx=x-.5;dy=.5-y
    sector=int(((math.atan2(dy,dx)+2*math.pi)%(2*math.pi)+math.pi/8)//(math.pi/4))%8
    radius=min(1.,math.hypot(dx,dy)*2)
    ring=0 if radius<1/3 else (1 if radius<2/3 else 2)
    zone=(sector,ring,c.get('harmony_root',9),c.get('harmony_scale','Menor natural (eòlica)'),c['channel'])
    with self.arp_lock:
      state=self.arp_states.get(i)
      if state and state['zone']==zone:return
    # 220 ms d'estabilització per evitar salts de nota en els límits.
    now=time.monotonic()
    candidate,since=self.harmony_pending.get(i,(None,now))
    if candidate!=zone:
      self.harmony_pending[i]=(zone,now);return
    if now-since<.22:return
    pitches=list(harmony_pitches(c,sector)[0])
    if ring==2:pitches=pitches[:2]
    elif ring==0:pitches.append(min(127,pitches[0]+12))
    self.stop_arpeggio(i)
    with self.arp_lock:
      self.arp_states[i]={'zone':zone,'pitches':pitches,'index':0,'last_step':None,'playing':None,'off_at':0}
    self.harmony_pending.pop(i,None)
 def stop_harmony(self,i):
    notes=self.harmony_notes.pop(i,[])
    if self.midi:
      for ch,note in notes:
        try:self.midi.send(mido.Message('note_off',channel=ch,note=note,velocity=0))
        except Exception:pass
    self.harmony_zones.pop(i,None);self.harmony_pending.pop(i,None);self.queued_harmony.pop(i,None)
 def spatial_harmony(self,i,x,y):
    # 8 sectors i 3 anells. Sense notes fins que es detecta la targeta.
    # Es manté el mateix acord mentre no es consolida un canvi de sector.
    c=self.cards[i]
    dx=x-.5;dy=.5-y
    angle=(math.atan2(dy,dx)+2*math.pi)%(2*math.pi)
    sector=int((angle+math.pi/8)//(math.pi/4))%8
    radius=min(1.,math.hypot(dx,dy)*2)
    ring=0 if radius<1/3 else (1 if radius<2/3 else 2)
    zone=(sector,ring,c.get('harmony_root',9),c.get('harmony_scale','Menor natural (eòlica)'),c['channel'])
    if self.harmony_zones.get(i)==zone or self.queued_harmony.get(i)==zone:
      self.harmony_pending.pop(i,None)
      return
    now=time.monotonic()
    candidate,since=self.harmony_pending.get(i,(None,now))
    if candidate!=zone:
      self.harmony_pending[i]=(zone,now)
      return
    if now-since<0.22:return
    if self.quantize_harmony.get():
      self.queued_harmony[i]=zone
      self.harmony_pending.pop(i,None)
    else:self.play_harmony_zone(i,zone)
 def play_harmony_zone(self,i,zone):
    if i not in self.active:return
    if self.harmony_zones.get(i)==zone:return
    c=self.cards[i]
    sector,ring=zone[0],zone[1]
    # L'escala determina els acords; els anells amplien l'octava i la densitat.
    triad=list(harmony_pitches(c,sector)[0])
    # Exterior: dues notes suaus; mig: tríada; interior: tríada + octava.
    pitches=triad[:2] if ring==2 else (triad if ring==1 else triad+[triad[0]+12])
    ch=max(0,min(15,int(c['channel'])-1))
    self.stop_harmony(i)
    velocity=max(1,min(127,int(c.get('harmony_velocity',85))))
    if self.midi:
      played=[]
      for note in pitches:
        try:
          self.midi.send(mido.Message('note_on',channel=ch,note=note,velocity=velocity))
          played.append((ch,note))
        except Exception as exc:self.status.set('Error harmonia MIDI: '+str(exc))
      self.harmony_notes[i]=played
    self.harmony_zones[i]=zone
    self.harmony_pending.pop(i,None)
 def activate(self,i,x,y,angle):
    c=self.cards[i];v={'Rotació':angle,'Horitzontal':x,'Vertical':y}.get(c['axis'],angle);v=max(0,min(1,v))
    was=i in self.active;self.active[i]=(x,y,angle)
    if not was and c.get('visual')==12:self.select_visual(12)
    if i==1 and c.get('function')=='Control MIDI CC' and c.get('cc')==7:
      self.activate_card2(x,y,angle)
      return
    if c['function']=='Harmonia espacial':
      self.spatial_harmony(i,x,y)
    elif c['function']=='Arpegiador espacial':
      self.spatial_arpeggio(i,x,y)
    elif c['function']=='Canviar visual' and not was:self.select_visual(c['visual'])
    elif c['function']=='Tempo':
      self.bpm=int(60+v*120)
      if self.bpm_var.get()!=self.bpm:self.bpm_var.set(self.bpm)
    elif c['function']=='Nota MIDI' and not was and self.midi:
      ch=c['channel']-1; note=c['note'];self.midi.send(mido.Message('note_on',channel=ch,note=note,velocity=100));self.notes[i]=(ch,note)
    elif c['function']=='Control MIDI CC' and self.midi:
      val=round(v*127)
      if self.last_cc.get(i)!=val:
        self.midi.send(mido.Message('control_change',channel=c['channel']-1,control=c['cc'],value=val));self.last_cc[i]=val
 def activate_card2(self,x,y,angle):
    # T02: volum radial CC7 i brillantor de filtre CC74 amb gir relatiu.
    channel=max(0,min(15,int(self.cards[1]['channel'])-1))
    radius=min(1.0,math.hypot((x-.5)*2,(y-.5)*2))
    self.card2_volume=int(round(radius*127))
    if self.card2_rotation_prev is None:
      self.card2_rotation_prev=angle
      self.card2_rotation_total=0.
    else:
      delta=((angle-self.card2_rotation_prev+0.5)%1)-0.5
      self.card2_rotation_total=max(-.25,min(.25,self.card2_rotation_total+delta))
      self.card2_rotation_prev=angle
    self.card2_filter=int(round(max(0,min(127,64-63*self.card2_rotation_total/.25))))
    if self.midi:
      for cc,value in ((7,self.card2_volume),(74,self.card2_filter)):
        key=(channel,cc)
        if self.card2_cc_values.get(key)!=value:
          try:
            self.midi.send(mido.Message('control_change',channel=channel,control=cc,value=value))
            self.card2_cc_values[key]=value
          except Exception as exc:self.status.set('Error MIDI T02: '+str(exc))
 def deactivate(self,i):
    self.stop_arpeggio(i)
    self.stop_harmony(i)
    self.active.pop(i,None);self.last_cc.pop(i,None)
    if self.cards[i].get('visual')==12 and not any(self.cards[j].get('visual')==12 for j in self.active):
      self.last_color_xy=None;self.smooth_color_xy=None
    if i==1:self.card2_rotation_prev=None;self.card2_rotation_total=0.
    if i in self.notes:
      ch,note=self.notes.pop(i)
      if self.midi:
        try:self.midi.send(mido.Message('note_off',channel=ch,note=note,velocity=0))
        except Exception:pass
 def render(self,t):
    # Procedural original visuals: offline, no external assets.
    yy,xx=np.mgrid[0:H,0:W].astype(np.float32);u=(xx-W/2)/(H/2);v=(yy-H/2)/(H/2);r=np.sqrt(u*u+v*v)+1e-4;a=np.arctan2(v,u)
    n=self.current_visual;beat=math.sin(t*self.bpm/60*math.pi*2); intensity=0.4+0.6*len(self.active)/16
    frame=np.zeros((H,W,3),np.uint8);frame[:]=(7,10,14)
    def rings(scale=8):
      z=np.sin(r*scale-t*2+np.sin(a*6+t)*.4);return np.clip((z-.35)*230,0,255).astype(np.uint8)
    if n==0:
      m=rings(19);frame[:,:,2]=m;frame[:,:,1]=m//3
      for k in range(12):
        ang=t*.3+k*math.tau/12;cv2.line(frame,(320,180),(int(320+150*math.cos(ang)),int(180+150*math.sin(ang))),(35,110,200),3)
      cv2.circle(frame,(320,180),int(38+beat*8),(30,125,240),5)
    elif n==1:
      noise=np.random.default_rng(int(t*8)).integers(0,80,(H,W),dtype=np.uint8);frame[:,:,2]=noise+35;frame[:,:,1]=noise//2+15
      for k in range(30):
        x=int((k*89+t*70*(1+k%3))%W);y=int((k*61+math.sin(t+k)*30)%H);cv2.line(frame,(x,y),(x-35,y+12),(30,95,180),1)
    elif n==2:
      f=np.sin(u*10+np.sin(v*8+t)*3+t)+np.cos(v*9-t*.6);z=np.clip((f+2)*50,0,255).astype(np.uint8);frame[:,:,1]=z;frame[:,:,2]=z//2;frame[:,:,0]=z//3
    elif n==3:
      m=rings(12);frame[:,:,0]=m;frame[:,:,2]=m//2
      rng=random.Random(int(t*6)); pts=[(rng.randrange(W),rng.randrange(H)) for _ in range(13)];cv2.polylines(frame,[np.array(pts,np.int32)],False,(80,190,255),2)
    elif n==4:
      z=np.abs(np.sin(a*10+t*.3))*np.abs(np.sin(12/(r+.1)-t*3));m=(z*240).astype(np.uint8);frame[:,:,2]=m;frame[:,:,1]=m//2
    elif n==5:
      m=rings(10);frame[:,:,2]=m;frame[:,:,1]=m//4
      rng=random.Random(int(t*5));
      for _ in range(60):
        x=rng.randrange(W);y=rng.randrange(H);cv2.circle(frame,(x,y),rng.randrange(1,4),(20,110,255),-1)
    elif n==6:
      rng=np.random.default_rng(int(t*12));m=rng.integers(0,256,(H,W),dtype=np.uint8);mask=(m>235);frame[mask]=(200,180,60)
      for _ in range(10):
        y=int(rng.integers(H));cv2.rectangle(frame,(0,y),(W,y+int(rng.integers(1,6))),(int(rng.integers(100)),80,170),-1)
    elif n==7:
      for k in range(13):
        points=[]
        for x in range(0,W,4):points.append((x,int(H/2+math.sin(x*.018+t*2+k*.3)*25+math.sin(x*.006-t+k)*k*4)))
        cv2.polylines(frame,[np.array(points,np.int32)],False,(30+k*5,90+k*6,170+k*5),1)
    elif n==8:
      rng=random.Random(47)
      for k in range(30):
        x=int((rng.randrange(W)+math.sin(t*.3+k)*35)%W);y=int((rng.randrange(H)+math.cos(t*.4+k)*35)%H);size=5+k%22
        cv2.rectangle(frame,(x-size,y-size),(x+size,y+size),(40+k*3,70+k*3,140+k*3),2)
    elif n==9:
      z=np.clip((1/(r+.15)+np.sin(a*8+t*2))*70,0,255).astype(np.uint8);frame[:,:,1]=z;frame[:,:,0]=z//3;cv2.circle(frame,(320,180),int(50+beat*10),(40,255,100),3)
    elif n==10:
      for k in range(14):
        ang=t*.2+k*math.tau/14;rad=20+k*11;cv2.ellipse(frame,(320,180),(rad,int(rad*.55)),int(ang*180/math.pi),10,260,(20+k*8,80+k*7,170+k*5),2)
      cv2.circle(frame,(320,180),int(24+beat*6),(70,200,240),-1)
    else:
      frame[:,:,2]=np.clip(25+100*np.exp(-((r-.8)**2)*12),0,255).astype(np.uint8)
      cv2.circle(frame,(320,200),int(65+beat*4),(30,95,230),-1);cv2.circle(frame,(320,200),int(65+beat*4),(15,50,150),4)
      for k in range(14):
        y=int(210+k*11);cv2.line(frame,(0,y),(W,y),(20,30+k*3,55+k*6),1)
    cv2.putText(frame,NAMES[n].upper(),(16,H-20),cv2.FONT_HERSHEY_SIMPLEX,.65,(160,195,225),1,cv2.LINE_AA)
    return frame
 def color_by_position(self,frame):
    chromatic_cards=[i for i in self.active if self.cards[i].get('visual')==12]
    if chromatic_cards:
      x,y,_=self.active[chromatic_cards[0]]
      self.last_color_xy=(x,y)
    now=time.monotonic()
    dt=max(0,min(.2,now-self.color_smooth_time)) if self.color_smooth_time is not None else 0
    self.color_smooth_time=now
    if self.last_color_xy is not None:
      if self.smooth_color_xy is None:self.smooth_color_xy=self.last_color_xy
      else:
        alpha=1-math.exp(-dt/max(.01,self.color_transition_seconds))
        self.smooth_color_xy=tuple(a+(b-a)*alpha for a,b in zip(self.smooth_color_xy,self.last_color_xy))
    return self.color_wheel_preview()
 def projection_color_frame(self):
    # Només el color que selecciona la targeta cromàtica, sense cap gràfic.
    # El color és exactament el del fons de la previsualització del cercle.
    if self.smooth_color_xy is None:
      bgr=(0,0,0)
    else:
      x,y=self.smooth_color_xy
      dx=(x-.5)*2;dy=(.5-y)*2
      degrees=(math.degrees(math.atan2(dy,dx))+360)%360
      radius=min(1.,math.hypot(dx,dy))
      hue=int(degrees/2)%180
      brightness=int((48+207*radius)*self.color_max_brightness)
      bgr=tuple(int(v) for v in cv2.cvtColor(
          np.uint8([[[hue,240,brightness]]]),cv2.COLOR_HSV2BGR)[0,0])
    return np.full((H,W,3),bgr,dtype=np.uint8)
 def harmony_map_preview(self,chromatic=False):
    # La base cromàtica i la capa musical comparteixen centre i radi.
    frame=self.color_by_position(None) if chromatic else np.full((H,W,3),(25,20,17),np.uint8)
    cards=[i for i in self.active if self.cards[i].get('function') in ('Harmonia espacial','Arpegiador espacial')]
    if not cards:return frame
    i=cards[0]
    x,y,_=self.active[i]
    dx=x-.5;dy=.5-y
    angle=(math.atan2(dy,dx)+math.tau)%math.tau
    sector=int((angle+math.pi/8)//(math.pi/4))%8
    radius=min(1.,math.hypot(dx,dy)*2)
    ring=0 if radius<1/3 else (1 if radius<2/3 else 2)
    cx,cy=W//2,H//2
    rr=int(min(H*.425,W*.32))
    yy,xx=np.ogrid[:H,:W]
    u=(xx-cx)/rr;v=(cy-yy)/rr
    rad=np.sqrt(u*u+v*v)
    theta=(np.arctan2(v,u)+math.tau)%math.tau
    sectors=np.floor((theta+math.pi/8)/(math.pi/4)).astype(np.int16)%8
    rings=np.where(rad<1/3,0,np.where(rad<2/3,1,2))
    mask=rad<=1
    if not chromatic:
      bg=np.full((H,W,3),(43,34,28),np.uint8)
      bg[(sectors%2==0)&mask]=(52,42,33)
      frame[mask]=bg[mask]
    selected=(sectors==sector)&(rings==ring)&mask
    # Barreja transparent, preservant els colors del disc.
    highlight=np.array([195,195,235],dtype=np.float32)
    frame[selected]=np.clip(frame[selected].astype(np.float32)*.60+highlight*.40,0,255).astype(np.uint8)
    for k in (1,2,3):
      cv2.circle(frame,(cx,cy),int(rr*k/3),(250,250,250),2,cv2.LINE_AA)
    for k in range(8):
      a=(k+0.5)*math.pi/4
      ex=int(cx+rr*math.cos(a));ey=int(cy-rr*math.sin(a))
      cv2.line(frame,(cx,cy),(ex,ey),(238,238,238),2,cv2.LINE_AA)
    chords=[harmony_pitches(self.cards[i],k)[1] for k in range(8)]
    for k,chord in enumerate(chords):
      a=k*math.pi/4
      px=int(cx+rr*.83*math.cos(a));py=int(cy-rr*.83*math.sin(a))
      # Contorn fosc per llegir els noms sobre qualsevol color.
      cv2.putText(frame,chord,(px-12,py+5),cv2.FONT_HERSHEY_SIMPLEX,.48,(12,12,12),3,cv2.LINE_AA)
      cv2.putText(frame,chord,(px-12,py+5),cv2.FONT_HERSHEY_SIMPLEX,.48,
                  (255,255,255) if k==sector else (225,220,208),1,cv2.LINE_AA)
    px=int(cx+radius*rr*math.cos(angle))
    py=int(cy-radius*rr*math.sin(angle))
    cv2.line(frame,(cx,cy),(px,py),(20,20,20),3,cv2.LINE_AA)
    cv2.line(frame,(cx,cy),(px,py),(250,240,170),1,cv2.LINE_AA)
    cv2.circle(frame,(px,py),11,(12,13,16),-1,cv2.LINE_AA)
    cv2.circle(frame,(px,py),7,(255,235,150),-1,cv2.LINE_AA)
    # Indicadors de totes les targetes arpegiadores (no només la primera).
    for j in cards:
      if self.cards[j].get('function')!='Arpegiador espacial':continue
      ax,ay,_=self.active[j]
      adx=ax-.5;ady=.5-ay
      aa=(math.atan2(ady,adx)+math.tau)%math.tau
      ar=min(1.,math.hypot(adx,ady)*2)
      ap=(int(cx+rr*ar*math.cos(aa)),int(cy-rr*ar*math.sin(aa)))
      cv2.circle(frame,ap,12,(20,20,20),-1,cv2.LINE_AA)
      cv2.circle(frame,ap,9,(50,205,255),-1,cv2.LINE_AA)
      cv2.putText(frame,str(j+1), (ap[0]-6,ap[1]+4),cv2.FONT_HERSHEY_SIMPLEX,.38,(10,10,10),1,cv2.LINE_AA)
    cv2.rectangle(frame,(0,0),(W,34),(16,14,14),-1)
    scale=NOTE_NAMES[int(self.cards[i].get('harmony_root',9))%12]+' '+self.cards[i].get('harmony_scale','Menor natural (eòlica)')
    cv2.putText(frame,f'HARMONIA + COLOR  |  TARGETA {i+1:02d}  |  {scale}' if chromatic else f'HARMONIA ESPACIAL  |  TARGETA {i+1:02d}  |  {scale}',
                (12,23),cv2.FONT_HERSHEY_SIMPLEX,.53,(245,228,205),1,cv2.LINE_AA)
    cv2.rectangle(frame,(0,H-32),(W,H),(16,14,14),-1)
    state=self.harmony_zones.get(i)
    if self.cards[i].get('function')=='Arpegiador espacial':
      with self.arp_lock:
        arp=self.arp_states.get(i)
        playing=arp.get('playing') if arp else None
      label=('ARPEGI: '+NOTE_NAMES[playing[1]%12] if playing else 'ARPEGI: ESPERANT PULS')
    else:
      label='SONANT' if state and state[:2]==(sector,ring) else 'CANVI PENDENT'
    layers=['INTERIOR: acord + octava','MIG: acord complet','EXTERIOR: dues notes']
    cv2.putText(frame,f'{chords[sector]}  |  SECTOR {sector+1}/8  |  {layers[ring]}  |  {label}',
                (10,H-11),cv2.FONT_HERSHEY_SIMPLEX,.49,(250,231,195),1,cv2.LINE_AA)
    return frame
 def color_wheel_preview(self):
    # Mapa gran de la pista i color projectat al voltant.
    result=np.empty((H,W,3),np.uint8)
    if self.smooth_color_xy is not None:
      x,y=self.smooth_color_xy
      dx=(x-.5)*2;dy=(.5-y)*2
      degrees=(math.degrees(math.atan2(dy,dx))+360)%360
      radius=min(1.,math.hypot(dx,dy))
      hue=int(degrees/2)%180
      brightness=int((48+207*radius)*self.color_max_brightness)
      rgb=cv2.cvtColor(np.uint8([[[hue,240,brightness]]]),cv2.COLOR_HSV2BGR)[0,0]
      result[:]=rgb
    else:
      dx=dy=degrees=radius=0
      result[:]=(22,18,20)
    # La roda ocupa la major part de l'altura, i el color real omple el fons.
    cx,cy=W//2,H//2
    rr=int(min(H*.425,W*.32))
    yy,xx=np.ogrid[:H,:W]
    xxn=(xx-cx)/rr
    yyn=(cy-yy)/rr
    rad=np.sqrt(xxn*xxn+yyn*yyn)
    degrees_map=(np.degrees(np.arctan2(yyn,xxn))+360)%360
    hsv=np.zeros((H,W,3),np.uint8)
    hsv[:,:,0]=(degrees_map/2).astype(np.uint8)
    hsv[:,:,1]=240
    hsv[:,:,2]=np.clip((48+207*np.minimum(rad,1))*self.color_max_brightness,0,255).astype(np.uint8)
    wheel=cv2.cvtColor(hsv,cv2.COLOR_HSV2BGR)
    result[rad<=1]=wheel[rad<=1]
    cv2.circle(result,(cx,cy),rr,(250,250,250),2,cv2.LINE_AA)
    cv2.circle(result,(cx,cy),rr//2,(245,245,245),1,cv2.LINE_AA)
    cv2.line(result,(cx-rr,cy),(cx+rr,cy),(235,235,235),1,cv2.LINE_AA)
    cv2.line(result,(cx,cy-rr),(cx,cy+rr),(235,235,235),1,cv2.LINE_AA)
    cv2.circle(result,(cx,cy),4,(255,255,255),-1,cv2.LINE_AA)
    if self.smooth_color_xy is not None:
      px=int(cx+dx*rr);py=int(cy-dy*rr)
      cv2.line(result,(cx,cy),(px,py),(245,245,245),2,cv2.LINE_AA)
      cv2.circle(result,(px,py),10,(0,0,0),-1,cv2.LINE_AA)
      cv2.circle(result,(px,py),7,(255,255,255),-1,cv2.LINE_AA)
    # Text sobre bandes fosques per llegibilitat.
    cv2.rectangle(result,(0,0),(W,32),(12,12,12),-1)
    if self.smooth_color_xy is not None:
      title=f'COLOR {degrees:.0f} graus  |  DISTANCIA {radius*100:.0f}%  |  SUAU 0.5 s'
    else:title='CERCLE CROMATIC 360 - TARGETA 01 (ID 0)'
    cv2.putText(result,title,(10,22),cv2.FONT_HERSHEY_SIMPLEX,.54,(255,255,255),1,cv2.LINE_AA)
    cv2.rectangle(result,(0,H-37),(W,H),(12,12,12),-1)
    if 1 in self.active:
      cv2.putText(result,f'T02  VOLUM {self.card2_volume*100//127}%  |  FILTRE CC74 {self.card2_filter}',
                  (12,H-14),cv2.FONT_HERSHEY_SIMPLEX,.6,(255,255,255),1,cv2.LINE_AA)
      cv2.rectangle(result,(400,H-30),(625,H-22),(55,55,55),-1)
      cv2.rectangle(result,(400,H-30),(400+int(225*self.card2_volume/127),H-22),(40,220,250),-1)
    else:
      cv2.putText(result,'T02: apropa la targeta per veure volum i filtre',
                  (12,H-14),cv2.FONT_HERSHEY_SIMPLEX,.51,(220,220,220),1,cv2.LINE_AA)
    return result
 def tick(self):
    try:
      self.musical_clock_tick()
      self.update_metronome_light()
      if self.camera:
        ok,frame=self.camera.read()
        if not ok:
          self.toggle_cam()
          self.status.set('S’ha perdut la imatge de la càmera. Torna-la a obrir.')
        if ok:
          # Detectem sobre la imatge ORIGINAL: els ArUco no admeten el reflex de mirall.
          gray=cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY)
          corners,ids,_=self.aruco_detector.detectMarkers(gray)
          now=time.monotonic();seen=set()
          if ids is not None:
            for points,raw in zip(corners,ids.flatten()):
              i=int(raw)
              if i>=16:continue
              p=points[0];cx=float(p[:,0].mean()/frame.shape[1]);cy=float(p[:,1].mean()/frame.shape[0]);dx=p[1]-p[0];angle=(math.atan2(float(dx[1]),float(dx[0]))%(math.tau))/math.tau
              seen.add(i);self.last_seen[i]=now;self.activate(i,cx,cy,angle)
              cv2.polylines(frame,[p.astype(np.int32)],True,(0,230,255),3)
              c=self.cards[i]
              v={'Rotació':angle,'Horitzontal':cx,'Vertical':cy}.get(c['axis'],angle)
              value=round(max(0,min(1,v))*127)
              label=f'T{i+1:02d} / ID {i}  {c["function"]}  {value}'
              if c.get('visual')==12 and self.current_visual==12:label+=f'  COLOR X:{cx*100:.0f}% Y:{cy*100:.0f}%'
              if i==1:label+=f'  VOL CC7:{self.card2_volume}  FILTRE CC74:{self.card2_filter}'
              tx=max(4,min(frame.shape[1]-320,int(p[:,0].min())))
              ty=max(20,int(p[:,1].min())-9)
              cv2.rectangle(frame,(tx-2,ty-18),(min(frame.shape[1]-1,tx+316),ty+5),(10,25,30),-1)
              cv2.putText(frame,label,(tx,ty),cv2.FONT_HERSHEY_SIMPLEX,.48,(0,240,255),1,cv2.LINE_AA)
          for i in list(self.active):
            if i not in seen and now-self.last_seen.get(i,now)>0.25:self.deactivate(i)
          # Mostrem la imatge original: els textos i els contorns es llegeixen correctament.
          if self.camera_window.state()=='normal':self.display(self.cam_label,cv2.cvtColor(frame,cv2.COLOR_BGR2RGB),'cam_photo')
      now_vis=time.monotonic()
      if self.last_frame is None or (not self.visual_paused and now_vis-self.last_visual_update>=self.visual_interval):
        t=now_vis-self.t0
        if any(self.cards[i].get('function') in ('Harmonia espacial','Arpegiador espacial') for i in self.active):
          self.last_frame=self.harmony_map_preview(chromatic=any(self.cards[j].get('visual')==12 for j in self.active))
        elif self.current_visual==12:
          self.last_frame=self.color_by_position(None)
        else:
          self.last_frame=self.render(t)
        self.last_visual_update=now_vis
        if self.visual_window.state()=='normal':self.display(self.vis_label,cv2.cvtColor(self.last_frame,cv2.COLOR_BGR2RGB),'vis_photo')
      vis=self.last_frame
      if getattr(self,'projection',None) and self.projection.winfo_exists():
        width=max(1,self.proj_label.winfo_width());height=max(1,self.proj_label.winfo_height())
        self.display(self.proj_label,cv2.cvtColor(cv2.resize(self.projection_color_frame(),(width,height)),cv2.COLOR_BGR2RGB),'proj_photo')
      if self.recording:self.recording.write(vis)
      self.monitor_ticks+=1
      if self.monitor_ticks%4==0:
        self.update_aruco_monitor();self.update_cards_table()
    except Exception as e:
      import traceback
      traceback.print_exc()
      self.status.set('Avís: '+str(e))
    if not self._closing:self.root.after(35,self.tick)
 def display(self,label,rgb,attr):
    # Escalem sense modificar la mida del widget; els dos monitors queden separats.
    available_w=max(1,label.winfo_width()-8)
    available_h=max(1,label.winfo_height()-8)
    h,w=rgb.shape[:2]
    factor=min(available_w/w,available_h/h)
    size=(max(1,int(w*factor)),max(1,int(h*factor)))
    if size!=(w,h):rgb=cv2.resize(rgb,size,interpolation=cv2.INTER_AREA if factor<1 else cv2.INTER_LINEAR)
    photo=ImageTk.PhotoImage(Image.fromarray(rgb))
    setattr(self,attr,photo);label.config(image=photo,text='')
 def close(self):
    self._closing=True
    self.arp_stop.set()
    self.arp_thread.join(timeout=1.0)
    self.all_notes_off()
    if self.recording:self.recording.release()
    if self.camera:self.camera.release()
    if self.midi:self.midi.close()
    self.root.destroy()

if __name__=='__main__':
 root=tk.Tk();App(root);root.mainloop()
