import os, sys, json, time, math, random, datetime, threading
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
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
FUNCS=['Nota MIDI','Harmonia espacial','Arpegiador espacial','Control MIDI CC','Canviar visual','Tempo','Patró rítmic','Ritme de bateria','Cap acció']
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
DRUM_NOTES={'Bombo':36,'Caixa':38,'Hi-hat tancat':42,'Hi-hat obert':46,'Crash':49}
# Un compàs 4/4 amb 16 semicorxeres; els passos interns comencen a zero.
DRUM_PRESETS={
 'Rock bàsic':{'Bombo':(0,8),'Caixa':(4,12),'Hi-hat tancat':tuple(range(0,16,2))},
 'Rock potent':{'Bombo':(0,2,8,10),'Caixa':(4,12),'Hi-hat tancat':tuple(range(0,16,2)),'Crash':(0,)},
 'Disco':{'Bombo':(0,4,8,12),'Caixa':(4,12),'Hi-hat tancat':(0,4,8,12),'Hi-hat obert':(2,6,10,14)},
 'Funk':{'Bombo':(0,3,6,10),'Caixa':(4,12),'Hi-hat tancat':tuple(range(16))},
 'Mig temps':{'Bombo':(0,7,10),'Caixa':(8,),'Hi-hat tancat':tuple(range(0,16,2))},
 'Electrònic':{'Bombo':(0,4,8,12),'Caixa':(4,12),'Hi-hat tancat':(2,6,10,14),'Hi-hat obert':(15,)},
}

ARP_DIRECTIONS=['Ascendent','Descendent','Pujada i baixada','Aleatori']

def arpeggio_note(pitches,index,direction):
    notes=sorted(pitches)
    if not notes:return None
    if direction=='Aleatori':return random.choice(notes)
    if direction=='Descendent':notes.reverse()
    elif direction=='Pujada i baixada' and len(notes)>1:notes=notes+notes[-2:0:-1]
    return notes[index%len(notes)]

class App:
 def __init__(self,root):
    self.root=root; root.title('WASTELAND MACHINE 4.5.15 · Pas 15 · Editor musical desplegable'); root.geometry('790x265'); root.minsize(570,205)
    self.cards=json.loads(json.dumps(DEFAULTS)); self.project='Sense títol'; self.bpm=120
    self.active={}; self.last_seen={}; self.last_cc={}; self.notes={}; self.harmony_notes={}; self.harmony_zones={}; self.harmony_pending={}; self.arp_states={}; self.arp_lock=threading.RLock(); self.arp_stop=threading.Event(); self.current_visual=0
    self.metronome_enabled=False; self.metronome_start=time.monotonic(); self.metronome_last_beat=-1; self.metronome_last_bpm=self.bpm; self.quantize_harmony=tk.BooleanVar(value=True); self.queued_harmony={}; self.clock_next_beat=1; self.clock_last_bpm=self.bpm
    self.show_only_assigned=tk.BooleanVar(value=True); self.visual_dirty=True; self.preview_card=None; self.preview_dirty=True; self.preview_caption=tk.StringVar(value='Previsualització en directe'); self.muted=False; self.sim_card=None; self.sim_xy=None; self.simulation=tk.BooleanVar(value=False); self.sim_angle=tk.DoubleVar(value=0); self.arp_direction=tk.StringVar(value='Ascendent'); self.rhythm_steps=[tk.BooleanVar(value=i%4==0) for i in range(16)]; self.drum_preset=tk.StringVar(value='Rock bàsic'); self.drum_notes={name:tk.IntVar(value=note) for name,note in DRUM_NOTES.items()}
    self.camera=None; self.midi=None; self.midi_name=''; self.recording=None; self.record_file=None; self.t0=time.monotonic(); self.last_frame=None; self.visual_paused=False; self.visual_paused_at=None; self.monitor_window=None; self.monitor_table=None; self.monitor_ticks=0
    self.aruco_detector=cv2.aruco.ArucoDetector(cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50))
    self.last_visual_update=0.0; self.visual_interval=1/12; self._closing=False
    yy,xx=np.mgrid[0:H,0:W].astype(np.float32); u=(xx-W/2)/(H/2); v=(yy-H/2)/(H/2)
    self._visual_coords=(u,v,np.sqrt(u*u+v*v)+1e-4,np.arctan2(v,u))
    self.last_color_xy=None; self.smooth_color_xy=None; self.color_smooth_time=None; self.color_transition_seconds=0.5; self.color_max_brightness=0.80; self.card2_rotation_prev=None; self.card2_rotation_total=0.0; self.card2_last_send=0.0; self.card2_cc_values={}; self.card2_volume=0; self.card2_filter=64; self.full=tk.BooleanVar(value=False); self.cam_index=tk.IntVar(value=0)
    self.harmony_key=tk.StringVar(value='La menor'); self.harmony_root=tk.StringVar(value='La'); self.harmony_scale=tk.StringVar(value='Menor natural (eòlica)'); self.bpm_var=tk.IntVar(value=self.bpm); self.harmony_velocity=tk.IntVar(value=85); self.arp_division=tk.StringVar(value='1/2 temps'); self.arp_gate=tk.IntVar(value=60); self.card_id=tk.StringVar(value='01'); self.fun=tk.StringVar(); self.axis=tk.StringVar(); self.note=tk.IntVar(); self.cc=tk.IntVar(); self.channel=tk.IntVar(); self.visual=tk.StringVar(); self.midi_choice=tk.StringVar(value='Sense MIDI'); self.status=tk.StringVar(value='Preparat · Obre la càmera per detectar les targetes')
    self.cards[0]['visual']=12; self.cards[1]['function']='Control MIDI CC'; self.cards[1]['cc']=7; self.cards[1]['axis']='Horitzontal'; self.build(); self.select_visual(12); self.load_card(); self.follow_live_preview(); self.refresh_midi(); self.root.protocol('WM_DELETE_WINDOW',self.close); self.root.after(50,self.tick); self.root.after(450,self.raise_all_panels); self.arp_thread=threading.Thread(target=self.arpeggio_worker,daemon=True); self.arp_thread.start()
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
    self.panic_button=tk.Button(toolbar,text='SILENCI ABSOLUT',command=self.toggle_panic,bg='#a52626',fg='white',font=('Segoe UI',10,'bold'));self.panic_button.pack(side='left',padx=3)
    ttk.Button(toolbar,text='TARGETES EN FUNCIÓ',command=lambda:self.show_panel('cards')).pack(side='left',padx=3)
    ttk.Button(toolbar,text='FINESTRES',command=self.show_all_panels).pack(side='left',padx=7)
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
    ttk.Label(self.visual_window,textvariable=self.preview_caption,wraplength=600).pack(fill='x',padx=5,pady=3)
    visual_content=ttk.Frame(self.visual_window);visual_content.pack(fill='both',expand=True)
    self.cards_window=self.make_panel_window('cards','TARGETES EN FUNCIÓ · MONITOR ARUCO','1180x520+60+100')
    self.cards_window.minsize(700,300)
    card_sidebar=ttk.Frame(self.cards_window);card_sidebar.pack(fill='both',expand=True,padx=8,pady=8)
    ttk.Label(card_sidebar,text='TARGETES EN FUNCIÓ · Doble clic al nom per editar-lo').pack(anchor='w',pady=(0,4))
    ttk.Checkbutton(card_sidebar,text='Només targetes amb funció',variable=self.show_only_assigned,command=self.update_assigned_cards).pack(anchor='w',pady=4)
    card_list=ttk.Frame(card_sidebar);card_list.pack(fill='both',expand=True)
    self.assigned_cards=ttk.Treeview(card_list,columns=('card','function','name','id','state','channel','note','cc','axis','value','x','y','angle','visual'),show='headings',selectmode='browse',height=8)
    self.assigned_cards.heading('card',text='Targeta');self.assigned_cards.column('card',width=58,minwidth=48,stretch=False)
    self.assigned_cards.heading('function',text='Funció');self.assigned_cards.column('function',width=165,minwidth=100)
    self.assigned_cards.heading('name',text='Nom assignat');self.assigned_cards.column('name',width=240,minwidth=120)
    for column,title,width in [('id','ID',38),('state','Estat',70),('channel','Canal',50),('note','Nota',48),('cc','CC',45),('axis','Eix',90),('value','Valor',55),('x','X %',55),('y','Y %',55),('angle','Graus',55),('visual','Visual',160)]:
      self.assigned_cards.heading(column,text=title);self.assigned_cards.column(column,width=width,minwidth=35,stretch=False)
    horizontal=ttk.Scrollbar(card_list,orient='horizontal',command=self.assigned_cards.xview)
    self.assigned_cards.configure(xscrollcommand=horizontal.set);horizontal.pack(side='bottom',fill='x')
    card_scroll=ttk.Scrollbar(card_list,orient='vertical',command=self.assigned_cards.yview)
    self.assigned_cards.configure(yscrollcommand=card_scroll.set)
    card_scroll.pack(side='right',fill='y');self.assigned_cards.pack(fill='both',expand=True)
    self.assigned_cards.tag_configure('active',background='#29453d',foreground='white')
    self.assigned_cards.bind('<<TreeviewSelect>>',self.choose_assigned_card)
    self.assigned_cards.bind('<Double-1>',self.edit_card_name)
    ttk.Button(card_sidebar,text='CANVIAR NOM DE LA TARGETA',command=self.edit_card_name).pack(fill='x',pady=(5,0))
    ttk.Button(card_sidebar,text='SEGUIR DIRECTE',command=self.follow_live_preview).pack(fill='x',pady=(5,0))
    self.cards_window.withdraw()
    self.vis_label=tk.Label(visual_content,bg='#0d0b0b',fg='#e0c3a0',anchor='center',bd=0)
    self.vis_label.pack(fill='both',expand=True,padx=5,pady=5)
    simulation_bar=ttk.Frame(self.visual_window);simulation_bar.pack(fill='x',padx=5,pady=3)
    ttk.Checkbutton(simulation_bar,text='SIMULAR AMB RATOLÍ',variable=self.simulation,command=self.toggle_simulation).pack(side='left')
    ttk.Label(simulation_bar,text='Gir').pack(side='left',padx=4)
    ttk.Scale(simulation_bar,from_=0,to=359,variable=self.sim_angle).pack(side='left',fill='x',expand=True)
    ttk.Label(self.visual_window,text='Targeta de l’editor · Mantén el clic i arrossega · Deixa anar per retirar-la').pack(fill='x',padx=5,pady=3)
    self.vis_label.bind('<ButtonPress-1>',self.simulation_press)
    self.vis_label.bind('<B1-Motion>',self.simulation_motion)
    self.root.bind_all('<ButtonRelease-1>',self.simulation_release,add='+')
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
    for label,var,vals in [('Funció',self.fun,FUNCS)]:
      ttk.Label(frame,text=label).pack(anchor='w',padx=8,pady=(5,0))
      combo=ttk.Combobox(frame,textvariable=var,values=vals,state='readonly',width=25)
      combo.pack(fill='x',padx=8)
      if label=='Funció':combo.bind('<<ComboboxSelected>>',self.on_function_selected)
    for label,var,from_,to in [('Canal MIDI (1-16)',self.channel,1,16),('Nota MIDI (0-127)',self.note,0,127)]:
      ttk.Label(frame,text=label).pack(anchor='w',padx=8,pady=(5,0))
      tk.Spinbox(frame,textvariable=var,from_=from_,to=to,width=8,bg='#e9d8c2').pack(anchor='w',padx=8)
    self.function_settings_button=ttk.Button(frame,text='CONFIGURAR FUNCIÓ…',command=self.open_function_settings)
    self.function_settings_button.pack(fill='x',padx=8,pady=(9,4))
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
    self.update_assigned_cards()
    if not hasattr(self,'cards_table'):return
    for i,c in enumerate(self.cards):
      val=(f'{i+1:02d}',c.get('name',f'Targeta {i+1:02d}'),c['function'],c['channel'],c['note'] if c['function']=='Nota MIDI' else c['cc'],NAMES[c['visual']] if c['function']=='Canviar visual' else '—',c['axis'])
      iid=str(i);tag='active' if i in self.active else ('odd' if i%2 else 'even')
      if self.cards_table.exists(iid):self.cards_table.item(iid,values=val,tags=(tag,))
      else:self.cards_table.insert('', 'end',iid=iid,values=val,tags=(tag,))
 def update_assigned_cards(self):
    if not hasattr(self,'assigned_cards'):return
    tree=self.assigned_cards
    ids={str(i) for i,c in enumerate(self.cards) if not self.show_only_assigned.get() or c.get('function','Cap acció')!='Cap acció'}
    for iid in tree.get_children():
      if iid not in ids:tree.delete(iid)
    for i,c in enumerate(self.cards):
      if str(i) not in ids:continue
      position=self.active.get(i)
      x,y,angle=position if position is not None else (None,None,None)
      value={'Rotació':angle,'Horitzontal':x,'Vertical':y}.get(c.get('axis'),angle)
      values=(f'{i+1:02d}',c['function'],c.get('name',f'Targeta {i+1:02d}'),i,'ACTIU' if position is not None else 'Inactiu',c['channel'],c['note'],c['cc'],c['axis'],round(max(0,min(1,value))*127) if value is not None else '--',f'{x*100:.1f}' if x is not None else '--',f'{y*100:.1f}' if y is not None else '--',f'{angle*360:.1f}' if angle is not None else '--',NAMES[c['visual']])
      tags=('active',) if i in self.active else ()
      if tree.exists(str(i)):tree.item(str(i),values=values,tags=tags)
      else:tree.insert('','end',iid=str(i),values=values,tags=tags)
    if self.preview_card is not None:
      if str(self.preview_card) not in ids:self.follow_live_preview()
      elif tree.selection()!=(str(self.preview_card),):tree.selection_set(str(self.preview_card))
 def edit_card_name(self,event=None):
    tree=self.assigned_cards
    if event is not None:
      if tree.identify_column(event.x)!='#3':return
      iid=tree.identify_row(event.y)
      if not iid:return
      tree.selection_set(iid)
    else:
      selected=tree.selection()
      if not selected:
        self.status.set('Selecciona una targeta per posar-hi nom.');return
      iid=selected[0]
    i=int(iid)
    name=simpledialog.askstring('Nom assignat',f'Nom per a la targeta {i+1:02d}:',initialvalue=self.cards[i].get('name',''),parent=self.cards_window)
    if name is None:return
    self.cards[i]['name']=name.strip()
    self.update_cards_table()
    if self.preview_card==i:self.select_card_preview(i)
    self.status.set(f'Nom de la targeta {i+1:02d} actualitzat. Desa el projecte per conservar-lo.')
 def choose_assigned_card(self,event=None):
    selected=self.assigned_cards.selection()
    if not selected:return
    i=int(selected[0])
    self.show_panel('visual')
    if self.preview_card==i and self.card_id.get()==f'{i+1:02d}':return
    self.simulation_release()
    self.card_id.set(f'{i+1:02d}');self.load_card()
    self.status.set(f'Targeta {i+1:02d}: mapa de configuració. Per provar-la, activa la simulació o ensenya la targeta.')
 def follow_live_preview(self):
    self.preview_card=None;self.preview_dirty=True
    self.preview_caption.set('Previsualització en directe' if self.active else 'Repòs · Cap targeta activa')
    selected=self.assigned_cards.selection()
    if selected:self.assigned_cards.selection_remove(*selected)
 def select_card_preview(self,i):
    if self.cards[i].get('function')=='Cap acció':
      self.follow_live_preview();return
    self.preview_card=i;self.preview_dirty=True
    c=self.cards[i]
    extra=c.get('drum_preset','Rock bàsic') if c['function']=='Ritme de bateria' else (c.get('arp_direction','Ascendent') if c['function']=='Arpegiador espacial' else f'Canal {c["channel"]}')
    self.preview_caption.set(f'Targeta {i+1:02d} · {c.get("name","")} · {c["function"]} · {extra} · Seleccionar no activa MIDI')
    self.update_assigned_cards()
 def card_preview_frame(self,i,t):
    c=self.cards[i];kind=c['function']
    if kind in ('Harmonia espacial','Arpegiador espacial'):
      return self.harmony_map_preview(chromatic=c.get('visual')==12,card_index=i)
    if kind in ('Patró rítmic','Ritme de bateria'):
      return self.rhythm_map_preview(i)
    if c.get('visual')==12:return self.color_wheel_preview()
    if kind=='Canviar visual':return self.render(t,visual=c['visual'])
    frame=np.full((H,W,3),(25,20,17),np.uint8)
    title=f'TARGETA {i+1:02d} | CANAL {c["channel"]}'
    cv2.putText(frame,title,(24,40),cv2.FONT_HERSHEY_SIMPLEX,.7,(245,228,205),1,cv2.LINE_AA)
    if kind=='Nota MIDI':
      text=f'NOTA MIDI {c["note"]}';detail='Clic premut: nota activa | Deixar anar: aturar'
    else:
      text=f'CONTROL CC {c["cc"]}' if kind=='Control MIDI CC' else 'TEMPO'
      detail={'Horitzontal':'ESQUERRA 0  --------------------  127 DRETA','Vertical':'DALT 0  --------------------  127 BAIX','Rotació':'GIR 0 - 359 graus'}.get(c.get('axis'),'')
    cv2.rectangle(frame,(24,78),(W-24,H-66),(125,100,75),2)
    cv2.putText(frame,text,(48,145),cv2.FONT_HERSHEY_SIMPLEX,1,(255,230,170),2,cv2.LINE_AA)
    cv2.putText(frame,detail,(32,H-36),cv2.FONT_HERSHEY_SIMPLEX,.5,(235,220,205),1,cv2.LINE_AA)
    if i in self.active:
      x,y,_=self.active[i];cv2.circle(frame,(int(x*(W-1)),int(y*(H-1))),10,(0,240,255),2)
    return frame
 def rhythm_map_preview(self,i):
    c=self.cards[i];drums=c['function']=='Ritme de bateria'
    rows=DRUM_PRESETS.get(c.get('drum_preset'),DRUM_PRESETS['Rock bàsic']) if drums else {'Nota '+str(c['note']):tuple(j for j,v in enumerate(c.get('rhythm_pattern',[k%4==0 for k in range(16)])) if v)}
    frame=np.full((H,W,3),(25,20,17),np.uint8)
    cv2.putText(frame,f'TARGETA {i+1:02d} | '+('BATERIA' if drums else 'PATRO RITMIC'),(12,27),cv2.FONT_HERSHEY_SIMPLEX,.65,(245,228,205),1,cv2.LINE_AA)
    current=None
    with self.arp_lock:
      state=self.arp_states.get(i)
      if state and state.get('last_step') is not None:
        current=(state['last_step']-state.get('origin_step',0))%16
    for step in range(16):
      cv2.putText(frame,str(step+1),(158+step*29,57),cv2.FONT_HERSHEY_SIMPLEX,.35,(230,220,200),1)
    for row,(name,steps) in enumerate(rows.items()):
      y=76+row*42
      label=name.replace('í','i').replace('à','a')
      cv2.putText(frame,label,(10,y+18),cv2.FONT_HERSHEY_SIMPLEX,.42,(240,225,205),1,cv2.LINE_AA)
      for step in range(16):
        x=154+step*29
        color=(65,185,235) if step in steps else (56,48,42)
        cv2.rectangle(frame,(x,y),(x+24,y+25),color,-1)
        if current==step:cv2.rectangle(frame,(x-1,y-1),(x+25,y+26),(255,255,255),2)
    cv2.putText(frame,'Clic premut o targeta present: reproduir | Retirar: aturar',(12,H-18),cv2.FONT_HERSHEY_SIMPLEX,.47,(230,215,195),1,cv2.LINE_AA)
    return frame
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
    # Compatibilitat amb les crides antigues: un únic monitor per a tot.
    self.show_panel('cards')
 def update_aruco_monitor(self):
    self.update_assigned_cards()
 def update_function_settings_button(self):
    kind=self.fun.get()
    enabled=kind in ('Control MIDI CC','Harmonia espacial','Arpegiador espacial','Patró rítmic','Ritme de bateria')
    self.function_settings_button.config(text='CONFIGURAR CONTROL MIDI CC…' if kind=='Control MIDI CC' else 'CONFIGURAR MÚSICA / PATRÓ…',state='normal' if enabled else 'disabled')
 def on_function_selected(self,event=None):
    self.update_function_settings_button()
    self.open_function_settings()
 def open_function_settings(self):
    if self.fun.get()=='Control MIDI CC':self.open_cc_settings()
    elif self.fun.get() in ('Harmonia espacial','Arpegiador espacial','Patró rítmic','Ritme de bateria'):self.open_music_settings()
 def open_cc_settings(self):
    old=getattr(self,'cc_settings_window',None)
    if old is not None and old.winfo_exists():old.destroy()
    win=tk.Toplevel(self.root);self.cc_settings_window=win
    win.title('CONTROL MIDI CC · TARGETA '+self.card_id.get());win.geometry('400x390');win.configure(bg='#151210');win.transient(self.root)
    pane=ttk.Frame(win);pane.pack(fill='both',expand=True,padx=16,pady=12)
    ttk.Label(pane,text='CONTROL MIDI CC',font=('Segoe UI',12,'bold')).pack(anchor='w',pady=8)
    for title,var,maximum,minimum in [('Canal MIDI',self.channel,16,1),('Número de controlador CC',self.cc,127,0)]:
      ttk.Label(pane,text=title).pack(anchor='w',pady=(6,2))
      tk.Spinbox(pane,textvariable=var,from_=minimum,to=maximum,width=8).pack(anchor='w')
    ttk.Label(pane,text='Moviment que controla el valor').pack(anchor='w',pady=(10,2))
    ttk.Combobox(pane,textvariable=self.axis,values=['Rotació','Horitzontal','Vertical'],state='readonly').pack(fill='x')
    ttk.Label(pane,text='T02 amb CC7 conserva el control especial: distància al centre = volum; gir = filtre CC74.',wraplength=360).pack(anchor='w',pady=10)
    ttk.Button(pane,text='APLICAR A LA TARGETA I TANCAR',command=lambda:(self.apply_card(),win.destroy())).pack(fill='x',pady=10)
 def open_music_settings(self):
    kind=self.fun.get()
    if kind not in ('Harmonia espacial','Arpegiador espacial','Patró rítmic','Ritme de bateria'):
      messagebox.showinfo('Configuració musical','Selecciona una funció musical: harmonia, arpegiador, patró rítmic o ritme de bateria.',parent=self.editor_window)
      return
    old=getattr(self,'music_settings_window',None)
    if old is not None and old.winfo_exists():
      old.destroy()
    win=tk.Toplevel(self.root)
    self.music_settings_window=win
    win.title('WASTELAND · '+kind.upper()+' · TARGETA '+self.card_id.get())
    win.geometry('460x700' if kind=='Ritme de bateria' else ('420x620' if kind in ('Arpegiador espacial','Patró rítmic') else '370x360'))
    win.minsize(320,275)
    win.configure(bg='#151210')
    win.transient(self.root)
    win.lift(self.root)
    pane=ttk.Frame(win);pane.pack(fill='both',expand=True,padx=16,pady=12)
    ttk.Label(pane,text=kind.upper(),foreground='#e7ae70',font=('Segoe UI',12,'bold')).pack(anchor='w',pady=(0,12))
    if kind not in ('Patró rítmic','Ritme de bateria'):
      ttk.Label(pane,text='Nota fonamental').pack(anchor='w',pady=(4,2))
      ttk.Combobox(pane,textvariable=self.harmony_root,values=NOTE_NAMES,state='readonly').pack(fill='x')
      ttk.Label(pane,text='Escala / mode').pack(anchor='w',pady=(9,2))
      ttk.Combobox(pane,textvariable=self.harmony_scale,values=list(SCALE_INTERVALS),state='readonly').pack(fill='x')
    ttk.Label(pane,text='Força de les notes MIDI (1–127)').pack(anchor='w',pady=(9,2))
    tk.Spinbox(pane,textvariable=self.harmony_velocity,from_=1,to=127,bg='#e9d8c2').pack(anchor='w')
    if kind in ('Arpegiador espacial','Patró rítmic'):
      ttk.Label(pane,text='Divisió rítmica').pack(anchor='w',pady=(10,2))
      ttk.Combobox(pane,textvariable=self.arp_division,values=['1 temps','1/2 temps','1/4 temps'],state='readonly').pack(fill='x')
      ttk.Label(pane,text='Durada de les notes (%)').pack(anchor='w',pady=(10,2))
      tk.Spinbox(pane,textvariable=self.arp_gate,from_=10,to=95,increment=5,bg='#e9d8c2').pack(anchor='w')
    if kind=='Arpegiador espacial':
      ttk.Label(pane,text='Direcció de les notes').pack(anchor='w',pady=(10,2))
      ttk.Combobox(pane,textvariable=self.arp_direction,values=ARP_DIRECTIONS,state='readonly').pack(fill='x')
    if kind=='Patró rítmic':
      ttk.Label(pane,text='16 passos · activa els cops que han de sonar').pack(anchor='w',pady=(12,4))
      steps=ttk.Frame(pane);steps.pack(fill='x')
      for j,var in enumerate(self.rhythm_steps):
        ttk.Checkbutton(steps,text=str(j+1),variable=var).grid(row=j//4,column=j%4,padx=5,pady=4)
      ttk.Label(pane,text='Utilitza la nota i el canal MIDI de la targeta. Per a bateria General MIDI, habitualment canal 10; nota 36: bombo, 38: caixa, 42: hi-hat.',wraplength=370).pack(anchor='w',pady=8)
    if kind=='Ritme de bateria':
      ttk.Label(pane,text='Ritme complet amb una sola targeta').pack(anchor='w',pady=(10,2))
      ttk.Combobox(pane,textvariable=self.drum_preset,values=list(DRUM_PRESETS),state='readonly').pack(fill='x')
      ttk.Label(pane,text='Canal MIDI de la pista de bateria (1–16)').pack(anchor='w',pady=(10,2))
      tk.Spinbox(pane,textvariable=self.channel,from_=1,to=16,bg='#e9d8c2').pack(anchor='w')
      ttk.Label(pane,text='Notes MIDI · adapta-les al mapa del teu instrument').pack(anchor='w',pady=(10,2))
      mapping=ttk.Frame(pane);mapping.pack(fill='x')
      for row,(name,var) in enumerate(self.drum_notes.items()):
        ttk.Label(mapping,text=name).grid(row=row,column=0,sticky='w',padx=4,pady=3)
        tk.Spinbox(mapping,textvariable=var,from_=0,to=127,width=6,bg='#e9d8c2').grid(row=row,column=1,padx=8,pady=3)
      ttk.Label(pane,text='Ensenya la targeta: sona el ritme. Retira-la: s’atura. Un compàs 4/4 al tempo del Wasteland. Ruta la sortida MIDI a MT Power Drum Kit dins de Sonar.',wraplength=390).pack(anchor='w',pady=10)
    ttk.Button(pane,text='APLICAR A LA TARGETA I TANCAR',command=lambda:(self.apply_card(),win.destroy())).pack(fill='x',pady=(16,4))
    ttk.Label(pane,text='Per conservar els canvis en disc: Projecte → Desar projecte.',wraplength=320).pack(anchor='w',pady=(5,0))
 def load_card(self):
    c=self.cards[int(self.card_id.get())-1]; self.fun.set(c['function']); self.axis.set(c['axis']); self.note.set(c['note']); self.cc.set(c['cc']); self.channel.set(c['channel']); self.visual.set(NAMES[c['visual']]); self.harmony_key.set(c.get('harmony_key','La menor')); self.harmony_root.set(NOTE_NAMES[int(c.get('harmony_root',9))%12]); self.harmony_scale.set(c.get('harmony_scale','Menor natural (eòlica)')); self.harmony_velocity.set(c.get('harmony_velocity',85)); self.arp_division.set(c.get('arp_division','1/2 temps')); self.arp_gate.set(c.get('arp_gate',60)); self.arp_direction.set(c.get('arp_direction','Ascendent'))
    self.drum_preset.set(c.get('drum_preset','Rock bàsic'))
    for name,var in self.drum_notes.items():var.set(c.get('drum_notes',{}).get(name,DRUM_NOTES[name]))
    for j,var in enumerate(self.rhythm_steps):var.set(bool(c.get('rhythm_pattern',[k%4==0 for k in range(16)])[j]))
    self.select_card_preview(int(self.card_id.get())-1)
    self.update_function_settings_button()
 def apply_card(self):
    try:
      card_index=int(self.card_id.get())-1
      self.deactivate(card_index)
      c=self.cards[card_index]; c.update(drum_preset=self.drum_preset.get(),drum_notes={name:max(0,min(127,int(var.get()))) for name,var in self.drum_notes.items()},arp_direction=self.arp_direction.get(),rhythm_pattern=[v.get() for v in self.rhythm_steps],arp_division=self.arp_division.get(),arp_gate=max(10,min(95,int(self.arp_gate.get()))),harmony_root=NOTE_NAMES.index(self.harmony_root.get()),harmony_scale=self.harmony_scale.get(),harmony_velocity=max(1,min(127,int(self.harmony_velocity.get()))),function=self.fun.get(),axis=self.axis.get(),note=max(0,min(127,int(self.note.get()))),cc=max(0,min(127,int(self.cc.get()))),channel=max(1,min(16,int(self.channel.get()))),visual=NAMES.index(self.visual.get()))
      if c['visual']==12 and int(self.card_id.get())-1 in self.active:self.select_visual(12)
      self.select_card_preview(card_index)
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
 def toggle_panic(self):
    with self.arp_lock:
      self.muted=not self.muted
      if self.muted:
        self.simulation_release()
        for i in list(self.active):self.deactivate(i)
        self.all_notes_off()
        self.harmony_pending.clear();self.last_cc.clear();self.card2_cc_values.clear()
        failures=0
        if self.midi:
          for channel in range(16):
            for control in (64,120,123):
              try:self.midi.send(mido.Message('control_change',channel=channel,control=control,value=0))
              except Exception:failures+=1
        self.panic_button.config(text='REPRENDRE MIDI',bg='#406c39')
        self.status.set('MIDI bloquejat. Prem REPRENDRE MIDI per continuar.' if not failures else 'MIDI bloquejat, però no s’ha pogut enviar tot el silenci al dispositiu. Comprova Cakewalk.')
      else:
        self.panic_button.config(text='SILENCI ABSOLUT',bg='#a52626')
        self.status.set('MIDI reprès. Torna a activar les targetes.')
 def toggle_simulation(self):
    self.simulation_release()
    if self.simulation.get() and self.camera:self.toggle_cam()
    self.status.set('Simulació: tria una targeta a l’editor i mantén el clic sobre la previsualització.' if self.simulation.get() else 'Simulació desactivada.')
 def simulation_position(self,event):
    # El mapa ocupa només la imatge centrada; els marges no són coordenades.
    width=self.vis_label.winfo_width();height=self.vis_label.winfo_height()
    scale=min(max(1,width-8)/W,max(1,height-8)/H)
    image_w=max(1,int(W*scale));image_h=max(1,int(H*scale))
    x=(event.x-(width-image_w)/2)/image_w
    y=(event.y-(height-image_h)/2)/image_h
    return (x,y) if 0<=x<=1 and 0<=y<=1 else None
 def simulation_press(self,event):
    if not self.simulation.get() or self.muted:return
    self.simulation_release()
    xy=self.simulation_position(event)
    if xy is None:return
    self.sim_card=int(self.card_id.get())-1;self.sim_xy=xy
    self.activate(self.sim_card,*xy,self.sim_angle.get()/360)
    self.status.set(f'Simulant targeta {self.sim_card+1:02d} · deixa anar el clic per retirar-la.')
 def simulation_motion(self,event):
    if self.sim_card is None:return
    xy=self.simulation_position(event)
    if xy is None:self.simulation_release();return
    self.sim_xy=xy
    self.activate(self.sim_card,*xy,self.sim_angle.get()/360)
 def simulation_release(self,event=None):
    if self.sim_card is not None:self.deactivate(self.sim_card)
    self.sim_card=None;self.sim_xy=None
 def toggle_cam(self):
    if self.camera:
      self.camera.release();self.camera=None
      for i in list(self.active):self.deactivate(i)
      self.all_notes_off()
      self.cam_label.config(image='',text='Càmera desconnectada')
      self.status.set('Càmera tancada');return
    if self.simulation.get():
      self.simulation.set(False);self.toggle_simulation()
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
    self.projection=tk.Toplevel(self.root);self.projection.title('PROJECCIÓ · WASTELAND MACHINE');self.projection.geometry('960x540');self.projection.configure(bg='black')
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
      if state:self.stop_drum_notes(state)
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
        if not self.muted:self.sequencer_tick(time.monotonic())
 def sequencer_tick(self,now):
    if self.muted:return
    for i,state in list(self.arp_states.items()):
      if self.cards[i]['function']=='Ritme de bateria':
        self.drum_tick(i,state,now);continue
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
      if c['function']=='Patró rítmic':
        pattern=c.get('rhythm_pattern',[j%4==0 for j in range(16)])
        if not pattern[step%16]:continue
        note=c['note']
      else:note=arpeggio_note(notes,state['index'],c.get('arp_direction','Ascendent'))
      state['index']+=1
      ch=max(0,min(15,int(c['channel'])-1))
      if self.midi:
        try:
          self.midi.send(mido.Message('note_on',channel=ch,note=note,velocity=max(1,min(127,int(c.get('harmony_velocity',85))))))
          state['playing']=(ch,note)
          # La durada també es calcula des de la graella absoluta.
          state['off_at']=self.metronome_start+(step+max(.1,min(.95,int(c.get('arp_gate',60))/100)))*interval
        except Exception:pass
 def stop_drum_notes(self,state):
    for channel,note in state.pop('playing_notes',[]):
      if self.midi:
        try:self.midi.send(mido.Message('note_off',channel=channel,note=note,velocity=0))
        except Exception:pass
 def drum_tick(self,i,state,now):
    if state.get('playing_notes') and now>=state.get('off_at',0):self.stop_drum_notes(state)
    interval=60.0/max(1,self.bpm)/4
    absolute_step=math.floor((now-self.metronome_start)/interval)
    if absolute_step<0 or absolute_step==state.get('last_step'):return
    state['last_step']=absolute_step
    self.stop_drum_notes(state)
    origin=state.setdefault('origin_step',absolute_step)
    step=(absolute_step-origin)%16
    c=self.cards[i]
    pattern=DRUM_PRESETS.get(c.get('drum_preset'),DRUM_PRESETS['Rock bàsic'])
    channel=max(0,min(15,int(c['channel'])-1))
    velocity=max(1,min(127,int(c.get('harmony_velocity',85))))
    played=[]
    for name,steps in pattern.items():
      if step not in steps:continue
      note=max(0,min(127,int(c.get('drum_notes',{}).get(name,DRUM_NOTES[name]))))
      if self.midi:
        try:
          self.midi.send(mido.Message('note_on',channel=channel,note=note,velocity=velocity))
          played.append((channel,note))
        except Exception:pass
    state['playing_notes']=played
    state['off_at']=self.metronome_start+(absolute_step+.4)*interval
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
    if self.muted:return
    c=self.cards[i];v={'Rotació':angle,'Horitzontal':x,'Vertical':y}.get(c['axis'],angle);v=max(0,min(1,v))
    was=i in self.active;self.active[i]=(x,y,angle)
    if not was:
      self.visual_dirty=True;self.follow_live_preview()
    if not was and c.get('visual')==12:self.select_visual(12)
    if i==1 and c.get('function')=='Control MIDI CC' and c.get('cc')==7:
      self.activate_card2(x,y,angle)
      return
    if c['function']=='Harmonia espacial':
      self.spatial_harmony(i,x,y)
    elif c['function'] in ('Patró rítmic','Ritme de bateria'):
      with self.arp_lock:
        if i not in self.arp_states:self.arp_states[i]={'pitches':[c['note']],'index':0,'last_step':None,'playing':None,'off_at':0}
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
    self.active.pop(i,None);self.last_cc.pop(i,None);self.visual_dirty=True;self.preview_dirty=True
    if self.cards[i].get('visual')==12 and not any(self.cards[j].get('visual')==12 for j in self.active):
      self.last_color_xy=None;self.smooth_color_xy=None
    if i==1:self.card2_rotation_prev=None;self.card2_rotation_total=0.
    if not self.active and self.preview_card is None:self.preview_caption.set('Repòs · Cap targeta activa')
    if i in self.notes:
      ch,note=self.notes.pop(i)
      if self.midi:
        try:self.midi.send(mido.Message('note_off',channel=ch,note=note,velocity=0))
        except Exception:pass
 def compose_live_visuals(self,t):
    visuals=sorted({int(self.cards[i].get('visual',0))%len(NAMES) for i in self.active if self.cards[i].get('function')!='Cap acció'})
    if not visuals:return np.zeros((H,W,3),np.uint8)
    if 12 in visuals:self.color_by_position(None)
    layers=[self.projection_color_frame() if n==12 else self.render(t,visual=n) for n in visuals]
    if len(layers)==1:return layers[0]
    # Mescla de tipus pantalla: els negres són transparents i les llums se superposen.
    remaining=np.ones((H,W,3),np.float32)
    gain=1/math.sqrt(len(layers))
    for layer in layers:remaining*=1-layer.astype(np.float32)*(gain/255)
    return np.clip((1-remaining)*255,0,255).astype(np.uint8)
 def render(self,t,visual=None):
    # Camps continus en coordenades precalculades: animació sense soroll aleatori.
    n=self.current_visual if visual is None else visual
    if n==12:return self.projection_color_frame()
    if not hasattr(self,'_render_coords'):self._render_coords=tuple(np.ascontiguousarray(coord[::2,::2]) for coord in self._visual_coords)
    u,v,r,a=self._render_coords
    phase=t*.45;beat=.5+.5*math.sin(t*self.bpm/60*math.tau)
    palettes=[
      ((8,6,13),(40,90,175),(155,220,255)),
      ((9,13,22),(44,96,145),(150,205,235)),
      ((12,12,5),(85,135,35),(205,255,125)),
      ((21,6,10),(160,55,85),(255,220,165)),
      ((12,7,18),(85,65,165),(225,205,255)),
      ((5,4,18),(20,65,205),(105,220,255)),
      ((20,12,4),(130,110,30),(255,245,170)),
      ((18,9,5),(125,80,35),(255,225,155)),
      ((20,5,12),(100,50,125),(240,185,235)),
      ((7,15,5),(45,150,55),(180,255,185)),
      ((9,7,12),(70,105,165),(205,235,255)),
      ((15,7,24),(50,75,170),(150,200,255)),
    ]
    if n==0:
      blades=np.cos(a*14-r*9+phase*2)
      field=np.exp(-((r-.67-.025*np.sin(a*7-phase))/.16)**2)*(.4+.6*np.maximum(0,blades)**3)
      field+=.3*np.exp(-((r-.24)/.045)**2)*(1+.25*beat)
    elif n==1:
      dunes=np.sin(v*5+np.sin(u*2+phase)*1.7+phase)
      field=(.5+.5*dunes)*.45+.45*np.exp(-((v+.2+np.sin(u*1.7-phase)*.2)/.15)**2)
      field*=np.exp(-r*.18)
    elif n==2:
      curl=np.sin(u*3+np.sin(v*4-phase))+np.cos(v*5+np.sin(u*3+phase))
      field=np.exp(-((curl-.35)/.45)**2)*(.5+.5*np.sin(a+phase)**2)
    elif n==3:
      arcs=np.sin(a*5+np.sin(r*6-phase)*2+phase)
      field=np.exp(-((r-.6-.13*arcs)/.025)**2)*.9
      field+=.32*np.exp(-((r-.6)/.22)**2)+.55*np.exp(-r*r*22)*(1+.2*beat)
    elif n==4:
      depth=1/(r+.23)
      field=(.5+.5*np.cos(depth*9-phase*5))**12*np.exp(-r*.8)
      field*=.55+.45*(.5+.5*np.cos(a*12+phase))
    elif n==5:
      flame=np.sin(u*5+np.sin(v*4+phase*3)*2)+np.sin(u*9-v*3+phase*4)*.4
      field=np.exp(-((flame-v*.65)/.7)**2)*np.clip((v+1.3)/2,0,1)
      field+=.28*np.exp(-((v-.6)/.25)**2)
    elif n==6:
      lattice=(np.maximum(0,np.cos(u*19+phase*1.3))**16+np.maximum(0,np.cos(v*25-phase*1.8))**20)*.35
      field=lattice*(.4+.6*np.sin(u*2+v*3+phase)**2)+.4*np.exp(-((v-.35*np.sin(u*2+phase))/.13)**2)
    elif n==7:
      waves=np.sin(v*10+np.sin(u*2-phase)*3+phase*2)
      field=(.5+.5*waves)**12*(.45+.55*np.cos(u*1.3+phase)**2)
      field+=.18*np.exp(-((v+.15)/.6)**2)
    elif n==8:
      swirl=a+r*3-phase
      field=np.exp(-((r-.65)/.22)**2)*(.3+.7*(.5+.5*np.cos(swirl*3))**4)
      for k in range(5):
        ang=phase*(.3+k*.06)+k*math.tau/5
        field+=.5*np.exp(-((u-math.cos(ang)*.85)**2+(v-math.sin(ang)*.55)**2)*170)
    elif n==9:
      field=.65*np.exp(-r*r*10)*(1+.25*beat)
      field+=.65*np.exp(-((r-.58-.035*math.sin(phase*3))/.04)**2)
      field+=(.5+.5*np.cos(r*26-phase*4))**14*np.exp(-r*2)*.3
    elif n==10:
      iris=(.5+.5*np.cos(a*65+np.sin(r*17-phase)*2))**5
      field=np.exp(-((r-.55)/.19)**2)*(.4+.6*iris)
      field+=.45*np.exp(-((r-.31)/.025)**2)+.5*np.exp(-((u+.23)**2+(v+.24)**2)*95)
    else:
      sun=np.sqrt((u*.85)**2+((v+.2)*1.1)**2)
      disc=np.clip((.46-sun)*100,0,1)
      stripes=.45+.55*(.5+.5*np.cos(v*65+phase))
      field=disc*stripes*.9+.25*np.exp(-sun*2)
      field+=.45*np.exp(-(u/(.12+np.maximum(v,0)*.8))**2)*np.clip(v,0,1)*(.5+.5*np.cos(v*40-phase*2))**4
    field=np.clip(field,0,1)
    dark,mid,light=(np.array(color,np.float32) for color in palettes[n%12])
    lower=np.minimum(1,field[...,None]*2)
    upper=np.maximum(0,field[...,None]*2-1)
    rgb=dark+(mid-dark)*lower+(light-mid)*upper
    # Halo suau i vinyeta: conservar detall a les llums i profunditat al fons.
    glow=cv2.GaussianBlur(np.maximum(rgb-95,0),(0,0),2)
    rgb=(rgb+glow*.55)*np.clip(1-r[...,None]*.18,.35,1)
    return cv2.resize(np.clip(rgb,0,255).astype(np.uint8),(W,H),interpolation=cv2.INTER_CUBIC)
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
 def harmony_map_preview(self,chromatic=False,card_index=None):
    # La base cromàtica i la capa musical comparteixen centre i radi.
    frame=(self.color_by_position(None) if card_index is None else self.color_wheel_preview()) if chromatic else np.full((H,W,3),(25,20,17),np.uint8)
    cards=[i for i in self.active if self.cards[i].get('function') in ('Harmonia espacial','Arpegiador espacial')]
    if card_index is not None:cards=[card_index]
    if not cards:return frame
    i=cards[0]
    position=self.active.get(i)
    x,y,_=position if position is not None else (.5,.5,0)
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
    selected=(sectors==sector)&(rings==ring)&mask if position is not None else np.zeros((H,W),bool)
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
    if position is not None:
      px=int(cx+radius*rr*math.cos(angle))
      py=int(cy-radius*rr*math.sin(angle))
      cv2.line(frame,(cx,cy),(px,py),(20,20,20),3,cv2.LINE_AA)
      cv2.line(frame,(cx,cy),(px,py),(250,240,170),1,cv2.LINE_AA)
      cv2.circle(frame,(px,py),11,(12,13,16),-1,cv2.LINE_AA)
      cv2.circle(frame,(px,py),7,(255,235,150),-1,cv2.LINE_AA)
    # Indicadors de totes les targetes arpegiadores (no només la primera).
    for j in cards:
      if j not in self.active or self.cards[j].get('function')!='Arpegiador espacial':continue
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
    footer=f'{chords[sector]}  |  SECTOR {sector+1}/8  |  {layers[ring]}  |  {label}' if position is not None else 'MAPA DE CONFIGURACIO | Targeta inactiva | Sense MIDI'
    cv2.putText(frame,footer,
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
      if self.sim_card is not None and self.sim_xy is not None and self.simulation.get():
        self.activate(self.sim_card,*self.sim_xy,self.sim_angle.get()/360)
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
      now_vis=time.monotonic();frame_changed=False
      if self.last_frame is None or self.visual_dirty or (not self.visual_paused and now_vis-self.last_visual_update>=self.visual_interval):
        t=now_vis-self.t0
        self.last_frame=self.compose_live_visuals(t)
        self.visual_dirty=False
        self.last_visual_update=now_vis;frame_changed=True
      if self.visual_window.state()=='normal' and (self.preview_dirty or frame_changed):
        preview=self.card_preview_frame(self.preview_card,now_vis-self.t0) if self.preview_card is not None else self.last_frame.copy()
        if self.sim_card is not None and self.sim_xy is not None:
          px,py=int(self.sim_xy[0]*(W-1)),int(self.sim_xy[1]*(H-1))
          cv2.circle(preview,(px,py),14,(0,240,255),2)
          cv2.putText(preview,f'SIM T{self.sim_card+1:02d}',(max(0,min(W-110,px+18)),max(20,py)),cv2.FONT_HERSHEY_SIMPLEX,.5,(0,240,255),1)
        self.display(self.vis_label,cv2.cvtColor(preview,cv2.COLOR_BGR2RGB),'vis_photo')
        self.preview_dirty=False
      vis=self.last_frame
      if getattr(self,'projection',None) and self.projection.winfo_exists():
        self.display(self.proj_label,cv2.cvtColor(self.last_frame,cv2.COLOR_BGR2RGB),'proj_photo')
      if self.recording:self.recording.write(vis)
      self.monitor_ticks+=1
      if self.monitor_ticks%4==0:
        self.update_cards_table()
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
