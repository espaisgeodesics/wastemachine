import os, sys, json, time, math, random, datetime, threading
from pathlib import Path
from collections import deque
from spatial_zones import SpatialMap
from spatial_projection import ZoneProjection
from spatial_zone_editor import ZoneEditor, rebase_map_images
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import numpy as np
import cv2
from PIL import Image, ImageTk, ImageDraw, ImageFont
try:
    import mido
except ImportError:
    mido = None

APP_VERSION='4.7.1'
CARD_LOST_TIMEOUT=.25
ROOT=Path(__file__).resolve().parent
(ROOT/'PROJECTES').mkdir(exist_ok=True)
(ROOT/'GRAVACIONS').mkdir(exist_ok=True)
W,H=640,360
NAMES=['Motor de ferro','Tempesta de pols','Vapor tòxic','Reactor elèctric','Túnel mecànic','Forja de foc','Fantasma digital','Ones mecàniques','Ferralla orbital','Nucli radioactiu','Ull de la màquina','Sol terminal','Cercle cromàtic 360°']
ZONE_FUNCTION='Activar zona espacial'
MUTE_FUNCTION='Control d’àudio / Mute'
FUNCS=['Nota MIDI','Harmonia espacial','Arpegiador espacial','Control MIDI CC','Canviar visual','Tempo','Patró rítmic','Ritme de bateria','Àudio',MUTE_FUNCTION,ZONE_FUNCTION,'Cap acció']
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

AUDIO_CONTROLS={
 'volume':{'label':'Volum','enabled':False,'cc':7,'axis':'Vertical','inverted':True,'min':0,'max':127},
 'pan':{'label':'Panoràmica','enabled':False,'cc':10,'axis':'Horitzontal','inverted':False,'min':0,'max':127},
 'effect':{'label':'Efecte assignable','enabled':False,'cc':74,'axis':'Rotació','inverted':False,'min':0,'max':127},
}
AUDIO_AXES=['Horitzontal','Vertical','Rotació','Distància al centre']

ARP_DIRECTIONS=['Ascendent','Descendent','Pujada i baixada','Aleatori']

def arpeggio_note(pitches,index,direction):
    notes=sorted(pitches)
    if not notes:return None
    if direction=='Aleatori':return random.choice(notes)
    if direction=='Descendent':notes.reverse()
    elif direction=='Pujada i baixada' and len(notes)>1:notes=notes+notes[-2:0:-1]
    return notes[index%len(notes)]

class TracedMidiOutput:
    """Report local send outcomes; this is not acknowledgement from the receiver."""
    def __init__(self,port,record):
        self._port=port;self._record=record
    def _trace(self,message,error):
        try:self._record(message,error)
        except Exception:pass  # Diagnostics must never change the MIDI stream.
    def send(self,message):
        try:self._port.send(message)
        except Exception as exc:
            self._trace(message,str(exc));raise
        self._trace(message,None)
    def close(self):self._port.close()
    def __getattr__(self,name):return getattr(self._port,name)

class App:
 def __init__(self,root):
    self.root=root; root.title('WASTELAND MACHINE · '+APP_VERSION); root.geometry('790x265'); root.minsize(570,205)
    self.card_name=tk.StringVar();self.master_volume=tk.DoubleVar(value=127);self.mixer_rows={};self.mixer_signature=None;self.monitor_details=tk.BooleanVar(value=False)
    self.midi_log=deque(maxlen=1000);self.midi_log_lock=threading.Lock();self.midi_log_revision=0;self.diagnostics_window=None;self.diagnostics_seen=-1
    self.spatial_map=SpatialMap();self.zone_projection=ZoneProjection(self.spatial_map);self.spatial_warning=None;self.zone_editor=None;self.zone_window=None
    self.cards=json.loads(json.dumps(DEFAULTS)); self.project='Sense títol'; self.bpm=120
    self.active={}; self.target_trails={}; self.last_seen={}; self.last_cc={}; self.notes={}; self.harmony_notes={}; self.harmony_zones={}; self.harmony_pending={}; self.arp_states={}; self.arp_lock=threading.RLock(); self.arp_stop=threading.Event(); self.current_visual=0
    self.clock_start=time.monotonic(); self.quantize_harmony=tk.BooleanVar(value=True); self.queued_harmony={}; self.clock_next_beat=1; self.clock_last_bpm=self.bpm
    self.show_only_assigned=tk.BooleanVar(value=True); self.visual_dirty=True; self.preview_card=None; self.preview_dirty=True; self.preview_caption=tk.StringVar(value='Previsualització en directe'); self.muted=False; self.sim_card=None; self.sim_xy=None; self.simulation=tk.BooleanVar(value=False); self.sim_angle=tk.DoubleVar(value=0); self.arp_direction=tk.StringVar(value='Ascendent'); self.rhythm_steps=[tk.BooleanVar(value=i%4==0) for i in range(16)]; self.drum_preset=tk.StringVar(value='Rock bàsic'); self.drum_notes={name:tk.IntVar(value=note) for name,note in DRUM_NOTES.items()}
    self.mute_audible=tk.IntVar(value=0);self.mute_silent=tk.IntVar(value=127);self.mute_sent={};self.mute_retry_after={}
    self.audio_states={}; self.audio_error=None; self.audio_duration=tk.DoubleVar(value=0);self.audio_cc_values={}
    self.audio_control_vars={}
    for role,defaults in AUDIO_CONTROLS.items():
      self.audio_control_vars[role]={key:(tk.BooleanVar(value=value) if key in ('enabled','inverted') else (tk.StringVar(value=value) if key=='axis' else tk.IntVar(value=value))) for key,value in defaults.items() if key!='label'}
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
    menu.add_cascade(label='Projecte',menu=fm)
    help_menu=tk.Menu(menu,tearoff=False);help_menu.add_command(label='Versió i fitxer que s’està executant',command=self.show_runtime_info)
    menu.add_cascade(label='Ajuda',menu=help_menu);self.root.config(menu=menu)
    banner=tk.Canvas(self.root,bg='#1c120e',height=60,highlightthickness=0)
    banner.pack(fill='x',padx=7,pady=(5,5))
    self.banner_source=None
    try:self.banner_source=Image.open(ROOT/'capcalera_wasteland_460.png').convert('RGB')
    except OSError:pass
    self.banner_canvas=banner;banner.bind('<Configure>',self.resize_banner)
    toolbar=ttk.Frame(self.root);toolbar.pack(fill='x',padx=9,pady=(1,5))
    self.panic_button=tk.Button(toolbar,text='SILENCI ABSOLUT',command=self.toggle_panic,bg='#a52626',fg='white',font=('Segoe UI',10,'bold'));self.panic_button.pack(side='left',padx=3)
    ttk.Button(toolbar,text='TARGETES EN FUNCIÓ',command=lambda:self.show_panel('cards')).pack(side='left',padx=3)
    ttk.Button(toolbar,text='ZONES ESPACIALS',command=self.open_zone_editor).pack(side='left',padx=3)
    ttk.Button(toolbar,text='TAULA DE VOLUMS',command=self.open_mixer).pack(side='left',padx=3)
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
    self.cards_window=self.make_panel_window('cards','TARGETES EN FUNCIÓ · MONITOR ARUCO','790x420+60+100')
    self.cards_window.minsize(600,300)
    card_sidebar=ttk.Frame(self.cards_window);card_sidebar.pack(fill='both',expand=True,padx=8,pady=8)
    ttk.Label(card_sidebar,text='TARGETES EN FUNCIÓ · Doble clic al nom per editar-lo').pack(anchor='w',pady=(0,4))
    ttk.Checkbutton(card_sidebar,text='Només targetes amb funció',variable=self.show_only_assigned,command=self.update_assigned_cards).pack(anchor='w',pady=4)
    ttk.Checkbutton(card_sidebar,text='Detall ArUco',variable=self.monitor_details,command=self.update_monitor_columns).pack(anchor='w',pady=2)
    card_list=ttk.Frame(card_sidebar);card_list.pack(fill='both',expand=True)
    self.assigned_cards=ttk.Treeview(card_list,columns=('card','function','name','id','state','channel','note','cc','axis','value','x','y','angle','visual','audio'),show='headings',selectmode='browse',height=8)
    self.assigned_cards.heading('card',text='Targeta');self.assigned_cards.column('card',width=58,minwidth=48,stretch=False)
    self.assigned_cards.heading('function',text='Funció');self.assigned_cards.column('function',width=165,minwidth=100)
    self.assigned_cards.heading('name',text='Nom assignat');self.assigned_cards.column('name',width=240,minwidth=120)
    for column,title,width in [('id','ID',38),('state','Estat',70),('channel','Canal',50),('note','Nota',48),('cc','CC',45),('axis','Eix',90),('value','Valor',55),('x','X %',55),('y','Y %',55),('angle','Graus',55),('visual','Visual',160),('audio','Àudio / Sonar',170)]:
      self.assigned_cards.heading(column,text=title);self.assigned_cards.column(column,width=width,minwidth=35,stretch=False)
    horizontal=ttk.Scrollbar(card_list,orient='horizontal',command=self.assigned_cards.xview)
    self.assigned_cards.configure(xscrollcommand=horizontal.set);horizontal.pack(side='bottom',fill='x')
    self.update_monitor_columns()
    card_scroll=ttk.Scrollbar(card_list,orient='vertical',command=self.assigned_cards.yview)
    self.assigned_cards.configure(yscrollcommand=card_scroll.set)
    card_scroll.pack(side='right',fill='y');self.assigned_cards.pack(fill='both',expand=True)
    self.assigned_cards.tag_configure('active',background='#29453d',foreground='white')
    self.assigned_cards.bind('<<TreeviewSelect>>',self.choose_assigned_card)
    self.assigned_cards.bind('<Double-1>',self.edit_card_name)
    ttk.Button(card_sidebar,text='SEGUIR DIRECTE',command=self.follow_live_preview).pack(fill='x',pady=(5,0))
    self.cards_window.withdraw()
    self.mixer_window=self.make_panel_window('mixer','TAULA DE VOLUMS','950x500+100+120')
    self.mixer_window.minsize(650,400)
    ttk.Label(self.mixer_window,text='Assigna cada CC al volum corresponent a Sonar amb MIDI Learn / ACT. El màster escala tots els volums.',wraplength=900).pack(fill='x',padx=10,pady=8)
    master=ttk.Frame(self.mixer_window);master.pack(fill='x',padx=10)
    ttk.Label(master,text='MÀSTER').pack(side='left',padx=5)
    ttk.Scale(master,from_=0,to=127,variable=self.master_volume,command=self.change_master_volume).pack(side='left',fill='x',expand=True,padx=10)
    self.master_label=ttk.Label(master,text='100 %',width=8);self.master_label.pack(side='right')
    holder=ttk.Frame(self.mixer_window);holder.pack(fill='both',expand=True,padx=8,pady=8)
    self.mixer_canvas=tk.Canvas(holder,bg='#151210',highlightthickness=0)
    scroll=ttk.Scrollbar(holder,orient='horizontal',command=self.mixer_canvas.xview)
    self.mixer_canvas.configure(xscrollcommand=scroll.set);scroll.pack(side='bottom',fill='x');self.mixer_canvas.pack(fill='both',expand=True)
    self.mixer_body=ttk.Frame(self.mixer_canvas);self.mixer_canvas.create_window((0,0),window=self.mixer_body,anchor='nw')
    self.mixer_body.bind('<Configure>',lambda e:self.mixer_canvas.configure(scrollregion=self.mixer_canvas.bbox('all')))
    self.mixer_window.withdraw()
    self.vis_label=tk.Label(visual_content,bg='#0d0b0b',fg='#e0c3a0',anchor='center',bd=0)
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
    ttk.Checkbutton(control_strip,text='ACORDS AL TEMPS',variable=self.quantize_harmony,command=self.toggle_quantization).pack(side='left',padx=(2,5))
    self.midi_cb=ttk.Combobox(midi_box,textvariable=self.midi_choice,width=26,state='readonly');self.midi_cb.pack(fill='x',padx=7,pady=(7,3))
    ttk.Button(midi_box,text='ACTUALITZAR PORTS',command=self.refresh_midi).pack(fill='x',padx=7,pady=2)
    ttk.Button(midi_box,text='CONNECTAR / FIXAR MIDI',command=self.connect_midi,style='Accent.TButton').pack(fill='x',padx=7,pady=3)
    midi_footer=ttk.Frame(midi_box);midi_footer.pack(fill='x',padx=7,pady=(1,6))
    self.midi_indicator=ttk.Label(midi_footer,text='Estat: desconnectat',foreground='#7de0ac')
    self.midi_indicator.pack(side='left',fill='x',expand=True)
    ttk.Button(midi_footer,text='DIAGNOSI MIDI',command=self.open_midi_diagnostics).pack(side='right',padx=3)
    self.midi_cb.bind('<<ComboboxSelected>>',lambda e:self.connect_midi())
    ttk.Label(frame,text='Targeta / ID ArUco').pack(anchor='w',padx=8,pady=(5,0))
    cb=ttk.Combobox(frame,textvariable=self.card_id,values=[f'{i+1:02d}' for i in range(16)],state='readonly',width=24)
    cb.pack(padx=8,fill='x');cb.bind('<<ComboboxSelected>>',lambda e:self.load_card())
    ttk.Label(frame,text='Nom assignat').pack(anchor='w',padx=8,pady=(7,2))
    self.card_name_entry=ttk.Entry(frame,textvariable=self.card_name);self.card_name_entry.pack(fill='x',padx=8,pady=(0,4))
    for label,var,vals in [('Funció',self.fun,FUNCS)]:
      ttk.Label(frame,text=label).pack(anchor='w',padx=8,pady=(5,0))
      combo=ttk.Combobox(frame,textvariable=var,values=vals,state='readonly',width=25)
      combo.pack(fill='x',padx=8)
      if label=='Funció':combo.bind('<<ComboboxSelected>>',self.on_function_selected)
    for label,var,from_,to in [('Canal MIDI (1-16)',self.channel,1,16),('Nota MIDI (0-127)',self.note,0,127)]:
      ttk.Label(frame,text=label).pack(anchor='w',padx=8,pady=(5,0))
      tk.Spinbox(frame,textvariable=var,from_=from_,to=to,width=8,bg='#e9d8c2').pack(anchor='w',padx=8)
    ttk.Label(frame,text='Tria o torna a seleccionar una funció per obrir-ne la configuració.',wraplength=245,foreground='#c9aa83').pack(anchor='w',padx=8,pady=(0,5))
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
      self.clock_start=now
      self.clock_next_beat=1
    interval=60.0/max(1,self.bpm)
    current=int((now-self.clock_start)/interval)
    if current>=self.clock_next_beat:
      # No reproduïm pulsacions acumulades després d'una aturada de la GUI.
      self.clock_next_beat=current+1
      if self.quantize_harmony.get():
        for i,zone in list(self.queued_harmony.items()):
          if i in self.active:self.play_harmony_zone(i,zone)
        self.queued_harmony.clear()
 def show_panel(self,key):
    win=self.panel_windows.get(key)
    if win and win.winfo_exists():
      win.deiconify()
      win.lift()
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
    width=max(250,(sw-3*margin)//2)
    height=max(140,(sh-top-3*margin-48)//2)
    layouts={
      'camera':(margin,top,width,height),
      'visual':(margin*2+width,top,width,height),
      'midi':(margin,top+height+margin,min(420,width),min(200,height)),
      'editor':(margin*2+width,top+height+margin,width,height),
    }
    self.initial_panel_layouts=layouts
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
    if self.window_layout_file.exists():
      self.restore_window_layout()
      if getattr(self,'loaded_layout_version',0)<3:
        for key in ('camera','visual','editor'):
          x,y,w,h=self.initial_panel_layouts[key];self.panel_windows[key].geometry(f'{w}x{h}+{x}+{y}')
 def save_window_layout(self):
    layout={'layout_version':3,'main':self.root.geometry(),'panels':{}}
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
      self.loaded_layout_version=layout.get('layout_version',0)
      if 'main' in layout:self.root.geometry(layout['main'])
      for key,data in layout.get('panels',{}).items():
        win=self.panel_windows.get(key)
        if not win or not win.winfo_exists():continue
        if 'geometry' in data:
          geometry=data['geometry']
          if key=='cards' and layout.get('layout_version',0)<2:
            import re
            match=re.match(r'(\d+)x(\d+)(.*)',geometry)
            if match and (int(match[1])>1000 or int(match[2])>520):geometry=f'{min(820,int(match[1]))}x{min(450,int(match[2]))}{match[3]}'
          win.geometry(geometry)
        if data.get('visible',True):
          win.deiconify()
          win.lift(self.root)
        else:win.withdraw()
      if not silent:self.status.set('Distribució de finestres recuperada.')
    except Exception as exc:
      self.status.set('No s’ha pogut recuperar la distribució: '+str(exc))
 def show_runtime_info(self):
    messagebox.showinfo('Wasteland · Versió i fitxer',f'Versió: {APP_VERSION}\n\nFitxer: {Path(__file__).resolve()}\n\nPython: {sys.executable}',parent=self.root)
 def resize_banner(self,event):
    width=max(1,event.width);height=min(112,max(48,round(width*.075)))
    self.banner_canvas.configure(height=height);self.banner_canvas.delete('all')
    if self.banner_source is None:
      self.banner_canvas.create_text(width/2,height/2,text='WASTELAND MACHINE',fill='#edbc88',font=('Georgia',23,'bold'));return
    image_height=round(self.banner_source.height*width/self.banner_source.width)
    self.banner_photo=ImageTk.PhotoImage(self.banner_source.resize((width,max(1,image_height)),Image.Resampling.LANCZOS))
    # El llenç mostra la franja panoràmica centrada, sense les vores del recurs.
    self.banner_canvas.create_image(width/2,height/2,image=self.banner_photo,anchor='center')
 def update_monitor_columns(self):
    self.assigned_cards.configure(displaycolumns='#all' if self.monitor_details.get() else ('card','name','function','state','channel','note','cc','value'))
 def mixer_config(self,i):
    c=self.cards[i]
    return dict({'channel':c['channel'],'cc':20+i,'level':100},**c.get('mixer',{}))
 def open_mixer(self):
    self.refresh_mixer();self.show_panel('mixer')
 def refresh_mixer(self,force=False):
    if not hasattr(self,'mixer_body'):return
    self.master_label.config(text=f'{round(self.master_volume.get()*100/127)} %')
    sources=[i for i,c in enumerate(self.cards) if c['function'] in ('Nota MIDI','Harmonia espacial','Arpegiador espacial','Patró rítmic','Ritme de bateria','Àudio')]
    signature=tuple(sources)
    if force or signature!=self.mixer_signature:
      for child in self.mixer_body.winfo_children():child.destroy()
      self.mixer_rows={};self.mixer_signature=signature
      if not sources:ttk.Label(self.mixer_body,text='Assigna una funció amb so a alguna targeta per veure’n el volum.').pack(padx=20,pady=40)
      for column,i in enumerate(sources):
        config=self.mixer_config(i);strip=ttk.LabelFrame(self.mixer_body,text=f'Targeta {i+1:02d}',padding=8);strip.grid(row=0,column=column,sticky='ns',padx=4,pady=4)
        name=ttk.Label(strip,text=self.cards[i].get('name',''),width=18,wraplength=135);name.pack(pady=4)
        variables={key:tk.DoubleVar(value=config[key]) if key=='level' else tk.IntVar(value=config[key]) for key in ('channel','cc','level')}
        level_label=ttk.Label(strip,text=f'{round(config["level"]*100/127)} %');level_label.pack()
        slider=tk.Scale(strip,from_=127,to=0,orient='vertical',variable=variables['level'],showvalue=False,length=175,bg='#261c16',fg='#edbc88',highlightthickness=0,command=lambda value,index=i:self.change_mixer_volume(index,value));slider.pack(pady=4)
        route=ttk.Frame(strip);route.pack()
        for title,key,minimum,maximum in [('Canal','channel',1,16),('CC','cc',0,127)]:
          line=ttk.Frame(route);line.pack(fill='x',pady=2);ttk.Label(line,text=title,width=6).pack(side='left')
          tk.Spinbox(line,from_=minimum,to=maximum,width=4,textvariable=variables[key]).pack(side='left')
        ttk.Button(strip,text='Enviar / Learn',command=lambda index=i:self.send_mixer_volume(index)).pack(fill='x',pady=(6,0))
        self.mixer_rows[i]={'variables':variables,'name':name,'label':level_label}
    for i,row in self.mixer_rows.items():row['name'].config(text=self.cards[i].get('name',f'Targeta {i+1:02d}'))
 def read_mixer_route(self,i):
    config=self.mixer_config(i)
    row=self.mixer_rows.get(i)
    if row:config={key:var.get() for key,var in row['variables'].items()}
    config={'channel':int(config['channel']),'cc':int(config['cc']),'level':max(0,min(127,float(config['level'])))}
    if not 1<=config['channel']<=16 or not 0<=config['cc']<=127:raise ValueError('Canal: 1–16; CC: 0–127.')
    for other,c in enumerate(self.cards):
      if other==i or c['function'] not in ('Nota MIDI','Harmonia espacial','Arpegiador espacial','Patró rítmic','Ritme de bateria','Àudio'):continue
      route=self.mixer_config(other)
      if (route['channel'],route['cc'])==(config['channel'],config['cc']):raise ValueError(f'La ruta coincideix amb la targeta {other+1:02d}. Assigna un altre canal o CC per controlar-les per separat.')
    self.cards[i]['mixer']=config
    return config
 def send_mixer_volume(self,i):
    try:config=self.read_mixer_route(i)
    except (ValueError,tk.TclError) as exc:self.status.set('Taula de volums: '+str(exc));return False
    if self.muted or not self.midi:
      self.status.set('Taula de volums: connecta la sortida MIDI i comprova que no estigui en silenci.');return False
    value=round(config['level']*self.master_volume.get()/127)
    try:self.midi.send(mido.Message('control_change',channel=config['channel']-1,control=config['cc'],value=value))
    except Exception as exc:self.status.set('Error de volum MIDI: '+str(exc));return False
    self.status.set(f'Volum T{i+1:02d}: CC{config["cc"]}, canal {config["channel"]}, valor {value}. Desa el projecte per conservar-lo.')
    return True
 def change_mixer_volume(self,i,value):
    row=self.mixer_rows.get(i)
    if not row:return
    level=max(0,min(127,float(value)));row['variables']['level'].set(level);row['label'].config(text=f'{round(level*100/127)} %')
    self.send_mixer_volume(i)
 def change_master_volume(self,value):
    if not hasattr(self,'master_label'):return
    self.master_volume.set(max(0,min(127,float(value))))
    self.master_label.config(text=f'{round(self.master_volume.get()*100/127)} %')
    try:
      for i in self.mixer_rows:self.read_mixer_route(i)
    except (ValueError,tk.TclError) as exc:
      self.status.set('Taula de volums: '+str(exc));return
    for i in self.mixer_rows:self.send_mixer_volume(i)
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
    self.refresh_mixer()
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
      reported=round(max(0,min(1,value))*127) if value is not None else '--'
      if c['function']==MUTE_FUNCTION:
        sent=self.mute_sent.get(i)
        reported=sent[2] if sent and sent[:2]==(c['channel']-1,c['cc']) else '--'
      values=(f'{i+1:02d}',c['function'],c.get('name',f'Targeta {i+1:02d}'),i,'ACTIU' if position is not None else 'Inactiu',c['channel'],c['note'],c['cc'],c['axis'],reported,f'{x*100:.1f}' if x is not None else '--',f'{y*100:.1f}' if y is not None else '--',f'{angle*360:.1f}' if angle is not None else '--',NAMES[c['visual']],self.audio_status(i))
      tags=('active',) if i in self.active else ()
      if tree.exists(str(i)):tree.item(str(i),values=values,tags=tags)
      else:tree.insert('','end',iid=str(i),values=values,tags=tags)
    if self.preview_card is not None:
      if str(self.preview_card) not in ids:self.follow_live_preview()
      elif tree.selection()!=(str(self.preview_card),):tree.selection_set(str(self.preview_card))
 def edit_card_name(self,event=None):
    tree=self.assigned_cards
    if event is not None:
      column=tree.identify_column(event.x)
      if not column or column=='#0':return
      columns=tuple(tree['columns']) if tuple(tree['displaycolumns'])==('#all',) else tuple(tree['displaycolumns'])
      if columns[int(column[1:])-1]!='name':return
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
    if self.card_id.get()==f'{i+1:02d}':self.card_name.set(name.strip())
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
    if kind==ZONE_FUNCTION:return self.zone_map_preview()
    if kind==MUTE_FUNCTION:
      frame=np.full((H,W,3),(25,20,17),np.uint8)
      for text,y in [(f'MUTE | TARGETA {i+1:02d}',45),(f'CANAL {c["channel"]} | CC {c["cc"]}',110),(f'VISIBLE: {c.get("mute_audible",0)} | ABSENT: {c.get("mute_silent",127)}',175),('Control de presencia | No envia notes MIDI',240)]:
        cv2.putText(frame,text,(24,y),cv2.FONT_HERSHEY_SIMPLEX,.65,(245,228,205),1,cv2.LINE_AA)
      return frame
    if kind=='Àudio':
      frame=np.full((H,W,3),(25,20,17),np.uint8)
      for text,y in [(f'AUDIO | TARGETA {i+1:02d}',45),(f'SONAR: CANAL {c["channel"]} | NOTA {c["note"]}',110),(f'UNA VEGADA | {c.get("audio_duration",0):g} segons',170),('Retirar la targeta no atura el clip.',240)]:
        cv2.putText(frame,text,(24,y),cv2.FONT_HERSHEY_SIMPLEX,.7,(245,228,205),1,cv2.LINE_AA)
      return frame
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
 def on_function_selected(self,event=None):
    self.open_function_settings()
 def open_function_settings(self):
    if self.fun.get()==ZONE_FUNCTION:self.open_zone_editor(default_card=int(self.card_id.get())-1)
    elif self.fun.get()==MUTE_FUNCTION:self.open_mute_settings()
    elif self.fun.get()=='Àudio':self.open_audio_settings()
    elif self.fun.get()=='Control MIDI CC':self.open_cc_settings()
    elif self.fun.get() in ('Harmonia espacial','Arpegiador espacial','Patró rítmic','Ritme de bateria'):self.open_music_settings()
 def zone_project_path(self):
    return None if self.project=='Sense títol' else self.project
 def open_zone_editor(self,default_card=None):
    if self.zone_window is None or not self.zone_window.winfo_exists():
      self.zone_window=self.make_panel_window('zones','EDITOR DE ZONES ESPACIALS','1080x660+60+60')
      self.zone_window.minsize(920,580)
      self.zone_editor=ZoneEditor(self.zone_window,self.spatial_map,lambda:self.cards,self.zone_project_path,self.apply_spatial_map,default_card)
    else:self.zone_editor.set_default_card(default_card)
    self.zone_editor.on_release=self.release_zone_scene
    self.show_panel('zones');self.update_spatial_editor_runtime()
 def apply_spatial_map(self,config):
    self.spatial_map=config;self.reset_spatial_projection(keep_scene=True)
    self.status.set('Mapa de zones actualitzat. Desa el projecte. Les activacions requereixen calibració vàlida.')
 def refresh_zone_editor(self):
    if self.zone_editor is not None:self.zone_editor.set_map(self.spatial_map)
 def reset_spatial_projection(self,keep_scene=False):
    self.zone_projection.configure(self.spatial_map,self.zone_project_path(),keep_scene=keep_scene)
    self.spatial_warning=None;self.visual_dirty=True;self.preview_dirty=True
    self.update_spatial_editor_runtime()
 def update_spatial_editor_runtime(self):
    if self.zone_editor is None:return
    player=self.zone_projection
    last=player.zone_name or 'cap'
    output={'zone':'fotografia persistent','color':'color cromàtic','live':'visuals en directe'}[player.mode]
    self.zone_editor.runtime_info.set(f'Última zona activada: {last} · Sortida: {output}'+(' · '+player.last_error if player.last_error else ''))
 def release_zone_scene(self):
    self.zone_projection.request_live();self.visual_dirty=True;self.preview_dirty=True;self.update_spatial_editor_runtime()
 def process_spatial_frame(self,zones,colors,now):
    player=self.zone_projection
    before=(player.mode,player.image.token if player.image else None,player.scene.zone_id if player.scene else None,player.color_card)
    if self.spatial_map.zones or colors or player.colors:
      player.process_camera(zones,colors,now)
    after=(player.mode,player.image.token if player.image else None,player.scene.zone_id if player.scene else None,player.color_card)
    if before!=after:self.visual_dirty=True;self.preview_dirty=True
    if player.last_error and player.last_error!=self.spatial_warning:
      self.status.set(player.last_error);self.spatial_warning=player.last_error
    self.update_spatial_editor_runtime()
 def compose_output_frame(self,t):
    player=self.zone_projection
    image=player.image_frame((W,H))
    if image is not None:return image
    if player.mode=='color' and player.color_card in self.active:
      self.color_by_position(None,card_index=player.color_card)
      return self.projection_color_frame()
    return self.compose_live_visuals(t)
 def projector_frame(self):
    player=self.zone_projection
    width=max(1,self.proj_label.winfo_width());height=max(1,self.proj_label.winfo_height())
    image=player.image_frame((width,height))
    if image is not None:return image
    if player.mode=='color' and player.color_card in self.active:return np.full((height,width,3),self.last_frame[0,0],np.uint8)
    return self.last_frame
 def zone_map_preview(self):
    frame=np.full((H,W,3),(25,20,17),np.uint8);radius=int(H*.40);left=W/2-radius;top=H/2-radius;diameter=2*radius
    grid=self.spatial_map.grid;colors=[(80,140,100),(145,100,160),(150,120,70),(65,150,190)]
    yy,xx=np.ogrid[:H,:W];circle=(xx-W/2)**2+(yy-H/2)**2<=radius**2
    for index,zone in enumerate(self.spatial_map.zones):
      if not zone.enabled:continue
      color=colors[index%len(colors)]
      if self.zone_projection.scene and zone.id==self.zone_projection.scene.zone_id:color=(75,195,235)
      for row,column in zone.cells:
        x0=round(left+column/grid.columns*diameter);x1=round(left+(column+1)/grid.columns*diameter)
        y0=round(top+row/grid.rows*diameter);y1=round(top+(row+1)/grid.rows*diameter)
        region=frame[y0:y1,x0:x1];mask=circle[y0:y1,x0:x1];region[mask]=color
    overlay=frame.copy()
    for column in range(grid.columns+1):
      x=round(left+column/grid.columns*diameter);cv2.line(overlay,(x,round(top)),(x,round(top+diameter)),(155,140,120),1)
    for row in range(grid.rows+1):
      y=round(top+row/grid.rows*diameter);cv2.line(overlay,(round(left),y),(round(left+diameter),y),(155,140,120),1)
    frame[circle]=overlay[circle];cv2.circle(frame,(W//2,H//2),radius,(240,215,180),2)
    calibration=self.spatial_map.calibration
    if calibration is not None:
      for i,(x,y,angle) in self.active.items():
        if self.cards[i]['function']!=ZONE_FUNCTION:continue
        point=calibration.project((x,y))
        if point is None or grid.cell_at(point) is None:continue
        trail=[]
        for stamp,tx,ty in self.target_trails.get(i,()):
          if time.monotonic()-stamp>2.5:continue
          floor_point=calibration.project((tx,ty))
          if floor_point is not None and grid.cell_at(floor_point) is not None:trail.append((round(left+floor_point[0]*diameter),round(top+floor_point[1]*diameter)))
        if len(trail)>1:cv2.polylines(frame,[np.array(trail,np.int32)],False,(200,200,200),1,cv2.LINE_AA)
        px=round(left+point[0]*diameter);py=round(top+point[1]*diameter)
        cv2.circle(frame,(px,py),8,(255,255,255),2)
        cv2.putText(frame,f'T{i+1:02d}',(px+10,max(45,py-10)),cv2.FONT_HERSHEY_SIMPLEX,.45,(255,255,255),1,cv2.LINE_AA)
    title='ZONES ESPACIALS | CALIBRACIO VALIDA' if calibration else 'ZONES | SENSE CALIBRACIO: ACTIVACIO BLOQUEJADA'
    cv2.putText(frame,title,(8,23),cv2.FONT_HERSHEY_SIMPLEX,.47,(245,225,195),1,cv2.LINE_AA)
    cv2.putText(frame,'Guies nomes a la previsualitzacio',(12,H-12),cv2.FONT_HERSHEY_SIMPLEX,.5,(245,225,195),1,cv2.LINE_AA)
    return frame
 def confirm_zone_discard(self):
    return self.zone_editor is None or self.zone_editor.confirm_discard()
 def open_mute_settings(self):
    old=getattr(self,'mute_settings_window',None)
    if old is not None and old.winfo_exists():old.destroy()
    if self.cards[int(self.card_id.get())-1]['function']!=MUTE_FUNCTION:
      self.cc.set(119);self.mute_audible.set(0);self.mute_silent.set(127)
    win=tk.Toplevel(self.root);self.mute_settings_window=win
    win.title('CONTROL D’ÀUDIO / MUTE · TARGETA '+self.card_id.get());win.geometry('460x480');win.transient(self.root);win.configure(bg='#151210')
    pane=ttk.Frame(win);pane.pack(fill='both',expand=True,padx=16,pady=12)
    ttk.Label(pane,text='PRESÈNCIA DE TARGETA → MUTE',font=('Segoe UI',11,'bold')).pack(anchor='w',pady=8)
    for title,var,minimum,maximum in [('Canal MIDI',self.channel,1,16),('Controlador CC',self.cc,0,119),('Visible → pista audible',self.mute_audible,0,127),('Absent → pista silenciada',self.mute_silent,0,127)]:
      ttk.Label(pane,text=title).pack(anchor='w',pady=(8,2))
      tk.Spinbox(pane,textvariable=var,from_=minimum,to=maximum,width=8).pack(anchor='w')
    ttk.Label(pane,text='Verificat a Sonar: canal 1, CC119, audible 0 i Mute 127. Assigna aquest mateix controlador al Mute de la pista amb Remote Control. No envia notes ni toca Play.',wraplength=420).pack(anchor='w',pady=12)
    ttk.Label(pane,text='En retirar la targeta s’envia Mute després de 250 ms. En aplicar o connectar, se sincronitza l’estat actual. Cada pista ha de tenir un canal + CC diferent.',wraplength=420).pack(anchor='w',pady=4)
    def apply():
      if self.apply_card():win.destroy()
    ttk.Button(pane,text='APLICAR A LA TARGETA I TANCAR',command=apply).pack(fill='x',pady=12)
 def open_audio_settings(self):
    old=getattr(self,'audio_settings_window',None)
    if old is not None and old.winfo_exists():old.destroy()
    win=tk.Toplevel(self.root);self.audio_settings_window=win
    win.title('ÀUDIO · DISPAR A SONAR · TARGETA '+self.card_id.get());win.geometry('560x700');win.transient(self.root);win.configure(bg='#151210')
    footer=ttk.Frame(win);footer.pack(side='bottom',fill='x',padx=16,pady=10)
    tabs=ttk.Notebook(win);tabs.pack(fill='both',expand=True,padx=12,pady=10)
    pane=ttk.Frame(tabs,padding=12);controls=ttk.Frame(tabs,padding=12)
    tabs.add(pane,text='Reproducció');tabs.add(controls,text='Moviment i efectes')
    ttk.Label(pane,text='ÀUDIO · UNA REPRODUCCIÓ COMPLETA',font=('Segoe UI',11,'bold')).pack(anchor='w',pady=8)
    for title,var,minimum,maximum,increment in [('Canal MIDI',self.channel,1,16,1),('Nota que activa el clip a Sonar',self.note,0,127,1),('Durada del clip en segons (obligatòria)',self.audio_duration,.1,86400,.1)]:
      ttk.Label(pane,text=title).pack(anchor='w',pady=(8,2))
      tk.Spinbox(pane,textvariable=var,from_=minimum,to=maximum,increment=increment,width=12).pack(anchor='w')
    ttk.Label(pane,text='A Sonar: carrega el clip en una cel·la Matrix o un sampler configurat en mode one-shot, sense bucle, i assigna-hi aquesta nota del port loopMIDI. Una pista normal no s’activa només rebent aquesta nota.',wraplength=420).pack(anchor='w',pady=(14,6))
    ttk.Label(pane,text='Retirar la targeta no atura el clip. Les deteccions es bloquegen durant els segons indicats. Quan acabi, retira i torna a ensenyar la targeta per repetir-lo. Sonar no ens envia confirmació del final: indica la durada real, incloent qualsevol espera de llançament.',wraplength=420).pack(anchor='w',pady=6)
    ttk.Label(controls,text='CONTROLS DE LA TARGETA',font=('Segoe UI',11,'bold')).pack(anchor='w',pady=(0,6))
    ttk.Label(controls,text='Activa només els controls vinculats amb MIDI Learn / ACT a Sonar o al plugin. Retirar la targeta manté l’últim valor; no envia volum zero ni atura el clip.',wraplength=500).pack(anchor='w',pady=(0,10))
    for role,variables in self.audio_control_vars.items():
      group=ttk.LabelFrame(controls,text=AUDIO_CONTROLS[role]['label'],padding=8);group.pack(fill='x',pady=5)
      ttk.Checkbutton(group,text='Activar',variable=variables['enabled']).grid(row=0,column=0,sticky='w')
      ttk.Label(group,text='CC').grid(row=0,column=1,padx=5)
      tk.Spinbox(group,textvariable=variables['cc'],from_=0,to=127,width=5).grid(row=0,column=2,sticky='w')
      ttk.Checkbutton(group,text='Invertir',variable=variables['inverted']).grid(row=0,column=3,padx=8)
      ttk.Combobox(group,textvariable=variables['axis'],values=AUDIO_AXES,state='readonly',width=22).grid(row=1,column=0,columnspan=2,sticky='w',pady=6)
      limits=ttk.Frame(group);limits.grid(row=1,column=2,columnspan=2,sticky='w')
      for title,key in [('Mín.','min'),('Màx.','max')]:
        ttk.Label(limits,text=title).pack(side='left',padx=3)
        tk.Spinbox(limits,textvariable=variables[key],from_=0,to=127,width=4).pack(side='left')
    self.audio_effect_preset=tk.StringVar(value='Personalitzat')
    ttk.Label(controls,text='Propostes de CC per a l’efecte (cal assignar-los al receptor)').pack(anchor='w',pady=(8,3))
    presets={'Filtre · CC74':74,'Reverberació · CC91':91,'Delay · CC94':94}
    preset=ttk.Combobox(controls,textvariable=self.audio_effect_preset,values=list(presets),state='readonly');preset.pack(fill='x')
    preset.bind('<<ComboboxSelected>>',lambda event:self.audio_control_vars['effect']['cc'].set(presets[self.audio_effect_preset.get()]))
    def apply():
      if self.apply_card():win.destroy()
    def test():
      if self.apply_card():self.trigger_audio(int(self.card_id.get())-1)
    ttk.Button(footer,text='PROVAR DISPAR A SONAR',command=test).pack(fill='x',pady=(10,0))
    ttk.Button(footer,text='APLICAR A LA TARGETA I TANCAR',command=apply).pack(fill='x',pady=12)
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
    self.card_name.set(c.get('name',f'Targeta {int(self.card_id.get()):02d}'))
    self.mute_audible.set(c.get('mute_audible',0));self.mute_silent.set(c.get('mute_silent',127))
    self.audio_duration.set(c.get('audio_duration',0))
    for role,variables in self.audio_control_vars.items():
      for key,var in variables.items():var.set(c.get('audio_controls',{}).get(role,{}).get(key,AUDIO_CONTROLS[role][key]))
    self.drum_preset.set(c.get('drum_preset','Rock bàsic'))
    for name,var in self.drum_notes.items():var.set(c.get('drum_notes',{}).get(name,DRUM_NOTES[name]))
    for j,var in enumerate(self.rhythm_steps):var.set(bool(c.get('rhythm_pattern',[k%4==0 for k in range(16)])[j]))
    self.select_card_preview(int(self.card_id.get())-1)
 def apply_card(self):
    try:
      card_index=int(self.card_id.get())-1
      duration=float(self.audio_duration.get())
      if not math.isfinite(duration) or duration<0 or (self.fun.get()=='Àudio' and duration<=0):raise ValueError('Indica la durada real del clip d’àudio en segons, superior a zero.')
      control_configs={role:{key:var.get() for key,var in variables.items()} for role,variables in self.audio_control_vars.items()}
      used=[]
      for config in control_configs.values():
        if config['axis'] not in AUDIO_AXES or not 0<=config['cc']<=127 or not 0<=config['min']<=config['max']<=127:raise ValueError('Revisa els CC i els límits dels controls d’àudio (0–127, mínim ≤ màxim).')
        if config['enabled']:used.append(config['cc'])
      if len(set(used))!=len(used):raise ValueError('Cada control d’àudio actiu ha de tenir un número CC diferent.')
      mute_values=(int(self.mute_audible.get()),int(self.mute_silent.get()))
      if self.fun.get()==MUTE_FUNCTION:
        if not 1<=int(self.channel.get())<=16 or not 0<=int(self.cc.get())<=119 or not all(0<=value<=127 for value in mute_values) or mute_values[0]==mute_values[1]:raise ValueError('Mute: canal 1–16, CC 0–119 i dos valors diferents entre 0 i 127.')
        for i,other in enumerate(self.cards):
          if i!=card_index and other['function']==MUTE_FUNCTION and (other['channel'],other['cc'])==(int(self.channel.get()),int(self.cc.get())):raise ValueError(f'La ruta Mute ja és de la targeta {i+1:02d}. Tria un altre canal o CC per a una pista independent.')
      previous=self.cards[card_index]
      same_mute=previous['function']==self.fun.get()==MUTE_FUNCTION
      if same_mute:
        if (previous['channel'],previous['cc'],previous.get('mute_silent',127))!=(int(self.channel.get()),int(self.cc.get()),mute_values[1]):self.send_mute_state(card_index,False)
      else:
        self.deactivate(card_index)
        self.mute_sent.pop(card_index,None);self.mute_retry_after.pop(card_index,None)
      c=self.cards[card_index]; c.update(mute_audible=mute_values[0],mute_silent=mute_values[1],name=self.card_name.get().strip(),audio_controls=control_configs,audio_duration=duration,drum_preset=self.drum_preset.get(),drum_notes={name:max(0,min(127,int(var.get()))) for name,var in self.drum_notes.items()},arp_direction=self.arp_direction.get(),rhythm_pattern=[v.get() for v in self.rhythm_steps],arp_division=self.arp_division.get(),arp_gate=max(10,min(95,int(self.arp_gate.get()))),harmony_root=NOTE_NAMES.index(self.harmony_root.get()),harmony_scale=self.harmony_scale.get(),harmony_velocity=max(1,min(127,int(self.harmony_velocity.get()))),function=self.fun.get(),axis=self.axis.get(),note=max(0,min(127,int(self.note.get()))),cc=max(0,min(127,int(self.cc.get()))),channel=max(1,min(16,int(self.channel.get()))),visual=NAMES.index(self.visual.get()))
      if c['visual']==12 and int(self.card_id.get())-1 in self.active:self.select_visual(12)
      self.select_card_preview(card_index)
      self.sync_mute_controls()
      self.status.set(f'Targeta {self.card_id.get()} configurada. Desa el projecte per conservar els canvis.');self.update_cards_table()
      return True
    except Exception as e:
      messagebox.showerror('Configuració',str(e));return False
 def new_project(self):
    if not self.confirm_zone_discard():return
    self.spatial_map=SpatialMap()
    self.all_notes_off(); self.cards=json.loads(json.dumps(DEFAULTS)); self.cards[0]['visual']=12; self.cards[1].update(function='Control MIDI CC',cc=7,axis='Horitzontal'); self.project='Sense títol';self.reset_mute_controls();self.master_volume.set(127);self.refresh_mixer(force=True); self.load_card();self.update_cards_table();self.reset_spatial_projection();self.refresh_zone_editor(); self.status.set('Projecte nou')
 def update_bpm(self):
    try:
      with self.arp_lock:
        self.bpm=max(40,min(180,int(self.bpm_var.get())))
        self.clock_start=time.monotonic()
        self.clock_last_bpm=self.bpm
        self.clock_next_beat=1
      self.bpm_var.set(self.bpm)
      self.status.set(f'Rellotge musical: {self.bpm} BPM. Acords quantitzats si activats; Cakewalk conserva el seu tempo.')
    except (ValueError,tk.TclError):self.status.set('Tempo no vàlid')
 def save_project(self,as_new=False):
    if self.zone_editor is not None and self.zone_editor.dirty:
      messagebox.showwarning('Zones espacials','Hi ha canvis de zona sense aplicar. Obre ZONES ESPACIALS i prem DESAR ZONA AL MAPA abans de desar el projecte.',parent=self.root);return
    if not self.apply_card():return
    try:
      for i in self.mixer_rows:self.read_mixer_route(i)
    except (ValueError,tk.TclError) as exc:
      messagebox.showerror('Taula de volums',str(exc));return
    old_project=self.zone_project_path()
    path=self.project
    if as_new or self.project=='Sense títol':
      path=filedialog.asksaveasfilename(initialdir=ROOT/'PROJECTES',defaultextension='.json',filetypes=[('Projecte Wasteland','*.json')])
      if not path:return
    try:
      spatial=rebase_map_images(self.spatial_map,old_project,path)
      data={'version':4,'master_volume':self.master_volume.get(),'cards':self.cards,'bpm':self.bpm,'quantize_harmony':self.quantize_harmony.get(),'visual':self.current_visual}
      data=spatial.into_project(data)
      with open(path,'w',encoding='utf-8') as f:json.dump(data,f,ensure_ascii=False,indent=2)
      self.project=path;self.spatial_map=spatial;self.reset_spatial_projection(keep_scene=True);self.refresh_zone_editor()
      self.status.set(f'Projecte desat: {Path(self.project).name}')
    except Exception as e:messagebox.showerror('Desar',str(e))
 def open_project(self):
    if not self.confirm_zone_discard():return
    path=filedialog.askopenfilename(initialdir=ROOT/'PROJECTES',filetypes=[('Projecte Wasteland','*.json')]);
    if not path:return
    try:
      with open(path,encoding='utf-8') as f:d=json.load(f)
      spatial=SpatialMap.from_project(d)
      if len(d['cards'])!=16:raise ValueError('El projecte no conté 16 targetes')
      self.all_notes_off(); self.cards=d['cards'];self.reset_mute_controls();self.master_volume.set(max(0,min(127,float(d.get('master_volume',127)))));self.refresh_mixer(force=True); self.bpm=d.get('bpm',120); self.bpm_var.set(self.bpm); self.quantize_harmony.set(d.get('quantize_harmony',True)); self.select_visual(int(d.get('visual',0))%len(NAMES)); self.project=path;self.spatial_map=spatial;self.reset_spatial_projection();self.refresh_zone_editor(); self.load_card();self.update_cards_table(); self.status.set('Projecte obert: '+Path(path).name)
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
 def log_midi_event(self,text):
    # Lazy initialization also allows isolated lifecycle tests without Tk.
    if not hasattr(self,'midi_log_lock'):
      self.midi_log_lock=threading.Lock();self.midi_log=deque(maxlen=1000);self.midi_log_revision=0
    line=datetime.datetime.now().isoformat(timespec='milliseconds')+' | '+text
    with self.midi_log_lock:self.midi_log.append(line);self.midi_log_revision+=1
 def record_midi_send(self,port,message,error=None):
    fields=[message.type]
    for key,label in [('channel','canal'),('note','nota'),('velocity','velocitat'),('control','CC'),('value','valor')]:
      if hasattr(message,key):fields.append(f'{label}={getattr(message,key)+(1 if key=="channel" else 0)}')
    outcome='ERROR LOCAL' if error is not None else 'ACCEPTAT PEL PORT LOCAL'
    self.log_midi_event(f'{outcome} [{port}] '+ ' '.join(fields)+(f' | {error}' if error is not None else ''))
 def midi_log_snapshot(self):
    with self.midi_log_lock:return '\n'.join(self.midi_log)
 def open_midi_diagnostics(self):
    if self.diagnostics_window is not None and self.diagnostics_window.winfo_exists():
      self.show_panel('diagnostic');self.update_midi_diagnostics();return
    win=self.make_panel_window('diagnostic','DIAGNOSI MIDI','940x550+80+100');self.diagnostics_window=win
    ttk.Label(win,text='Registre LOCAL: no confirma recepció a Sonar ni l’estat del Mute. Canals: 1–16. Absència ArUco: 250 ms.',wraplength=900).pack(fill='x',padx=10,pady=8)
    holder=ttk.Frame(win);holder.pack(fill='both',expand=True,padx=10,pady=4)
    self.diagnostics_text=tk.Text(holder,height=16,wrap='none',font=('Consolas',9),bg='#171411',fg='#f2dcc4',state='disabled')
    scroll=ttk.Scrollbar(holder,orient='vertical',command=self.diagnostics_text.yview);scroll.pack(side='right',fill='y')
    self.diagnostics_text.configure(yscrollcommand=scroll.set);self.diagnostics_text.pack(fill='both',expand=True)
    tools=ttk.Frame(win);tools.pack(fill='x',padx=10,pady=5)
    ttk.Button(tools,text='COPIAR REGISTRE',command=self.copy_midi_log).pack(side='left',padx=3)
    ttk.Button(tools,text='DESAR REGISTRE…',command=self.save_midi_log).pack(side='left',padx=3)
    ttk.Button(tools,text='NETEJAR',command=self.clear_midi_log).pack(side='left',padx=3)
    test=ttk.LabelFrame(win,text='Prova CC explícit per verificar Remote Control a Sonar',padding=8);test.pack(fill='x',padx=10,pady=(4,10))
    self.probe_channel=tk.IntVar(value=1);self.probe_cc=tk.IntVar(value=119)
    for title,var,minimum,maximum in [('Canal',self.probe_channel,1,16),('CC',self.probe_cc,0,127)]:
      ttk.Label(test,text=title).pack(side='left',padx=4)
      tk.Spinbox(test,from_=minimum,to=maximum,textvariable=var,width=5).pack(side='left')
    ttk.Button(test,text='ENVIAR 0',command=lambda:self.send_probe_cc(0)).pack(side='left',padx=8)
    ttk.Button(test,text='ENVIAR 127',command=lambda:self.send_probe_cc(127)).pack(side='left',padx=8)
    self.log_midi_event(f'DIAGNOSI {APP_VERSION} | Fitxer: {Path(__file__).resolve()} | No hi ha confirmació del receptor.')
    self.update_midi_diagnostics()
 def update_midi_diagnostics(self):
    if self.diagnostics_window is None or not self.diagnostics_window.winfo_exists() or self.diagnostics_window.state()=='withdrawn':return
    with self.midi_log_lock:
      revision=self.midi_log_revision
      if revision==self.diagnostics_seen:return
      text='\n'.join(self.midi_log)
    self.diagnostics_text.configure(state='normal');self.diagnostics_text.delete('1.0','end');self.diagnostics_text.insert('end',text)
    self.diagnostics_text.see('end');self.diagnostics_text.configure(state='disabled');self.diagnostics_seen=revision
 def copy_midi_log(self):
    self.root.clipboard_clear();self.root.clipboard_append(self.midi_log_snapshot());self.status.set('Registre MIDI local copiat.')
 def clear_midi_log(self):
    with self.midi_log_lock:self.midi_log.clear();self.midi_log_revision+=1
    self.update_midi_diagnostics()
 def save_midi_log(self):
    path=filedialog.asksaveasfilename(parent=self.diagnostics_window,defaultextension='.txt',initialfile='diagnosi_midi.txt',filetypes=[('Registre de text','*.txt')])
    if not path:return
    try:Path(path).write_text(self.midi_log_snapshot(),encoding='utf-8')
    except OSError as exc:messagebox.showerror('Diagnosi MIDI',str(exc),parent=self.diagnostics_window)
 def send_probe_cc(self,value):
    if self.muted or not self.midi:
      self.status.set('Connecta MIDI i desactiva el silenci abans de provar el CC.');return
    try:
      channel=int(self.probe_channel.get());control=int(self.probe_cc.get())
      if not 1<=channel<=16 or not 0<=control<=127 or value not in (0,127):raise ValueError('Canal 1–16, CC 0–127 i valor 0 o 127.')
      self.midi.send(mido.Message('control_change',channel=channel-1,control=control,value=value))
    except Exception as exc:self.status.set('Error a la prova CC: '+str(exc))
 def expire_missing_cards(self,seen,now):
    for i in list(self.active):
      if i not in seen and now-self.last_seen.get(i,now)>CARD_LOST_TIMEOUT:self.deactivate(i)
 def connect_midi(self):
    self.all_notes_off()
    if self.midi:
      try:self.midi.close()
      except Exception:pass
    self.midi=None;self.mute_sent.clear();self.mute_retry_after.clear(); self.card2_cc_values.clear(); name=self.midi_choice.get()
    if name=='Sense MIDI':
      self.status.set('MIDI desconnectat');self.midi_indicator.config(text='Estat: desconnectat');return
    try:
      port=mido.open_output(name)
      self.midi=TracedMidiOutput(port,lambda message,error:self.record_midi_send(name,message,error))
      self.log_midi_event('CONNEXIÓ LOCAL: '+name)
      self.status.set('MIDI connectat a '+name)
      self.midi_indicator.config(text='CONNECTAT: '+name)
      self.sync_mute_controls()
    except Exception as e:
      self.log_midi_event('ERROR DE CONNEXIÓ LOCAL: '+str(e))
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
    if not (0<=x<=1 and 0<=y<=1):return None
    if self.radial_preview():
      rr=int(min(H*.425,W*.32))
      x=.5+(x*W-W/2)/(2*rr);y=.5+(y*H-H/2)/(2*rr)
      x=max(0,min(1,x));y=max(0,min(1,y))
    return x,y
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
    self.sync_mute_controls(silence=True)
    with self.arp_lock:
      for state in self.audio_states.values():self.release_audio_trigger(state)
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
        now=time.monotonic();self.audio_tick(now)
        if not self.muted:self.sequencer_tick(now)
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
      step=math.floor((now-self.clock_start)/interval)
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
          state['off_at']=self.clock_start+(step+max(.1,min(.95,int(c.get('arp_gate',60))/100)))*interval
        except Exception:pass
 def stop_drum_notes(self,state):
    for channel,note in state.pop('playing_notes',[]):
      if self.midi:
        try:self.midi.send(mido.Message('note_off',channel=channel,note=note,velocity=0))
        except Exception:pass
 def drum_tick(self,i,state,now):
    if state.get('playing_notes') and now>=state.get('off_at',0):self.stop_drum_notes(state)
    interval=60.0/max(1,self.bpm)/4
    absolute_step=math.floor((now-self.clock_start)/interval)
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
    state['off_at']=self.clock_start+(absolute_step+.4)*interval
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
 def send_audio_controls(self,i,x,y,angle,force=False):
    if self.muted or not self.midi:return
    c=self.cards[i];channel=max(0,min(15,int(c['channel'])-1))
    cache=self.audio_cc_values.setdefault(i,{})
    if force:cache.clear()
    axes={'Horitzontal':x,'Vertical':y,'Rotació':angle,'Distància al centre':min(1,math.hypot((x-.5)*2,(y-.5)*2))}
    for role,defaults in AUDIO_CONTROLS.items():
      config=dict(defaults,**c.get('audio_controls',{}).get(role,{}))
      if not config['enabled']:continue
      value=max(0,min(1,axes.get(config['axis'],0)))
      if config['inverted']:value=1-value
      value=round(config['min']+(config['max']-config['min'])*value)
      key=(channel,int(config['cc']))
      if cache.get(key)==value:continue
      try:
        self.midi.send(mido.Message('control_change',channel=channel,control=key[1],value=value))
        cache[key]=value
      except Exception as exc:self.status.set('Error de control d’àudio MIDI: '+str(exc))
 def audio_status(self,i):
    with self.arp_lock:
      state=self.audio_states.get(i)
      remaining=state['ends_at']-time.monotonic() if state else 0
    if remaining>0:return f'Dispar bloquejat · {remaining:.1f} s'
    return 'Preparat' if self.cards[i].get('function')=='Àudio' else '—'
 def trigger_audio(self,i):
    if self.muted:
      self.status.set('Àudio: prem REPRENDRE MIDI abans d’enviar un dispar.');return
    c=self.cards[i]
    if not self.midi:
      self.status.set('Àudio: connecta primer la sortida MIDI que rep Sonar.');return
    duration=float(c.get('audio_duration',0))
    if not math.isfinite(duration) or duration<=0:
      self.status.set('Àudio: configura la durada real del clip abans d’activar-lo.');return
    now=time.monotonic();channel=max(0,min(15,int(c['channel'])-1));note=max(0,min(127,int(c['note'])))
    with self.arp_lock:
      self.audio_tick(now)
      if any(state['ends_at']>now and (key==i or (state['channel'],state['note'])==(channel,note)) for key,state in self.audio_states.items()):return
      old=self.audio_states.pop(i,None)
      if old:self.release_audio_trigger(old)
      try:self.midi.send(mido.Message('note_on',channel=channel,note=note,velocity=100))
      except Exception as exc:
        self.status.set('No s’ha pogut enviar el dispar d’àudio: '+str(exc));return
      self.audio_states[i]={'channel':channel,'note':note,'ends_at':now+duration,'release_at':now+min(.08,duration),'trigger_down':True}
    self.status.set(f'Dispar d’àudio enviat a Sonar · Targeta {i+1:02d} · bloqueig {duration:g} s. Comprova la reproducció a Sonar.')
 def release_audio_trigger(self,state):
    if not state.get('trigger_down'):return
    if self.midi:
      try:self.midi.send(mido.Message('note_off',channel=state['channel'],note=state['note'],velocity=0))
      except Exception as exc:self.audio_error='Error alliberant el dispar MIDI d’àudio: '+str(exc)
    state['trigger_down']=False
 def audio_tick(self,now):
    # El note_off acaba el pols de dispar, no la reproducció one-shot de Sonar.
    for i,state in list(self.audio_states.items()):
      if now>=state['release_at']:self.release_audio_trigger(state)
      if now>=state['ends_at']:self.audio_states.pop(i,None)
 def send_mute_state(self,i,audible):
    c=self.cards[i]
    if c['function']!=MUTE_FUNCTION or not self.midi:return False
    audible=bool(audible and not self.muted and not getattr(self,'_closing',False))
    state=(int(c['channel'])-1,int(c['cc']),int(c.get('mute_audible',0) if audible else c.get('mute_silent',127)))
    if self.mute_sent.get(i)==state:return True
    now=time.monotonic()
    if now<self.mute_retry_after.get(i,0):return False
    try:self.midi.send(mido.Message('control_change',channel=state[0],control=state[1],value=state[2]))
    except Exception as exc:
      self.mute_retry_after[i]=now+.5
      self.status.set('Error enviant Mute; es tornarà a provar: '+str(exc));return False
    self.mute_sent[i]=state;self.mute_retry_after.pop(i,None)
    return True
 def sync_mute_controls(self,silence=False):
    for i,c in enumerate(self.cards):
      if c['function']==MUTE_FUNCTION:self.send_mute_state(i,not silence and i in self.active)
 def reset_mute_controls(self):
    self.mute_sent.clear();self.mute_retry_after.clear()
    # Un projecte nou comença absent fins al següent fotograma de detecció.
    for i,c in enumerate(self.cards):
      if c['function']==MUTE_FUNCTION:self.active.pop(i,None);self.target_trails.pop(i,None)
    self.sync_mute_controls()
 def record_target_position(self,i,x,y):
    now=time.monotonic();trail=self.target_trails.setdefault(i,deque(maxlen=90))
    if not trail or math.hypot(x-trail[-1][1],y-trail[-1][2])>.002 or now-trail[-1][0]>.08:trail.append((now,x,y))
    while trail and now-trail[0][0]>2.5:trail.popleft()
 def radial_preview(self):
    cards=[self.preview_card] if self.preview_card is not None else list(self.active)
    if not cards and self.simulation.get():cards=[int(self.card_id.get())-1]
    return any(self.cards[i]['function']!=ZONE_FUNCTION and (self.cards[i].get('visual')==12 or self.cards[i].get('function') in ('Harmonia espacial','Arpegiador espacial')) for i in cards)
 def tracking_point(self,x,y,radial=False):
    if not radial:return (round(max(0,min(1,x))*(W-1)),round(max(0,min(1,y))*(H-1)))
    dx=(x-.5)*2;dy=(y-.5)*2;length=max(1,math.hypot(dx,dy))
    rr=int(min(H*.425,W*.32))
    return (round(W/2+dx/length*rr),round(H/2+dy/length*rr))
 def live_preview_frame(self):
    if self.zone_projection.mode!='color' and (self.zone_projection.mode=='zone' or any(self.cards[i]['function']==ZONE_FUNCTION for i in self.active)):return self.zone_map_preview()
    if not self.active:return self.last_frame.copy()
    musical=[i for i in self.active if self.cards[i].get('function') in ('Harmonia espacial','Arpegiador espacial')]
    chromatic=any(self.cards[i]['function']!=ZONE_FUNCTION and self.cards[i].get('visual')==12 for i in self.active)
    if musical:frame=self.harmony_map_preview(chromatic=chromatic,card_index=musical[0])
    elif chromatic:frame=self.color_wheel_preview()
    else:frame=self.last_frame.copy()
    radial=bool(musical or chromatic);now=time.monotonic()
    colors=[(70,210,255),(255,185,70),(150,255,120),(235,120,245)]
    for i,(x,y,angle) in self.active.items():
      color=colors[i%len(colors)]
      points=[self.tracking_point(tx,ty,radial) for stamp,tx,ty in self.target_trails.get(i,()) if now-stamp<=2.5]
      if len(points)>1:cv2.polylines(frame,[np.array(points,np.int32)],False,color,2,cv2.LINE_AA)
      px,py=self.tracking_point(x,y,radial)
      cv2.circle(frame,(px,py),11,(8,8,8),-1,cv2.LINE_AA)
      cv2.circle(frame,(px,py),8,color,2,cv2.LINE_AA)
      dx=int(16*math.cos(angle*math.tau));dy=int(16*math.sin(angle*math.tau))
      cv2.line(frame,(px,py),(px+dx,py+dy),color,2,cv2.LINE_AA)
      label=('SIM ' if i==self.sim_card else '')+f'T{i+1:02d}'
      tx=max(3,min(W-100,px+16));ty=max(20,min(H-40,py-12))
      cv2.putText(frame,label,(tx,ty),cv2.FONT_HERSHEY_SIMPLEX,.48,(8,8,8),3,cv2.LINE_AA)
      cv2.putText(frame,label,(tx,ty),cv2.FONT_HERSHEY_SIMPLEX,.48,color,1,cv2.LINE_AA)
    return frame
 def activate(self,i,x,y,angle):
    if self.muted:return
    c=self.cards[i];v={'Rotació':angle,'Horitzontal':x,'Vertical':y}.get(c['axis'],angle);v=max(0,min(1,v))
    was=i in self.active;self.active[i]=(x,y,angle)
    self.record_target_position(i,x,y)
    if not was:
      self.log_midi_event(f'VISIBLE T{i+1:02d} ID={i} funció={c["function"]}')
      self.visual_dirty=True;self.follow_live_preview()
    if not was and c['function']!=ZONE_FUNCTION and c.get('visual')==12:self.select_visual(12)
    if i==1 and c.get('function')=='Control MIDI CC' and c.get('cc')==7:
      self.activate_card2(x,y,angle)
      return
    if c['function']==ZONE_FUNCTION:return
    if c['function']==MUTE_FUNCTION:
      self.send_mute_state(i,True)
    elif c['function']=='Àudio':
      self.send_audio_controls(i,x,y,angle,force=not was)
      if not was:self.trigger_audio(i)
    elif c['function']=='Harmonia espacial':
      self.spatial_harmony(i,x,y)
    elif c['function'] in ('Patró rítmic','Ritme de bateria'):
      with self.arp_lock:
        if i not in self.arp_states:self.arp_states[i]={'pitches':[c['note']],'index':0,'last_step':None,'playing':None,'off_at':0}
    elif c['function']=='Arpegiador espacial':
      self.spatial_arpeggio(i,x,y)
    elif c['function']=='Canviar visual' and not was:
      if c['visual']!=12:self.zone_projection.request_live()
      self.select_visual(c['visual'])
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
    if self.cards[i]['function']==MUTE_FUNCTION:self.send_mute_state(i,False)
    if i in self.active:self.log_midi_event(f'RETIRADA T{i+1:02d} ID={i}')
    self.stop_arpeggio(i)
    self.stop_harmony(i)
    self.active.pop(i,None);self.target_trails.pop(i,None);self.last_cc.pop(i,None);self.audio_cc_values.pop(i,None);self.visual_dirty=True;self.preview_dirty=True
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
    visuals=sorted({int(self.cards[i].get('visual',0))%len(NAMES) for i in self.active if self.cards[i].get('function') not in ('Cap acció',ZONE_FUNCTION)})
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
 def color_by_position(self,frame,card_index=None):
    chromatic_cards=[i for i in self.active if self.cards[i].get('visual')==12]
    if card_index in chromatic_cards:chromatic_cards=[card_index]
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
      px,py=self.tracking_point(x,y,radial=True)
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
      if self.audio_error:
        self.status.set(self.audio_error);self.audio_error=None
      self.musical_clock_tick()
      zone_observations={};color_observations={}
      if self.sim_card is not None and self.sim_xy is not None and self.simulation.get():
        self.activate(self.sim_card,*self.sim_xy,self.sim_angle.get()/360)
        card=self.cards[self.sim_card]
        if card['function']==ZONE_FUNCTION:zone_observations[self.sim_card]=self.sim_xy
        elif card['visual']==12 and card['function']!='Cap acció':color_observations[self.sim_card]=self.sim_xy
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
              if c['function']==ZONE_FUNCTION:zone_observations[i]=(cx,cy)
              elif c['visual']==12 and c['function']!='Cap acció':color_observations[i]=(cx,cy)
              v={'Rotació':angle,'Horitzontal':cx,'Vertical':cy}.get(c['axis'],angle)
              value=round(max(0,min(1,v))*127)
              label=f'T{i+1:02d} / ID {i}  {c["function"]}  {value}'
              if c.get('visual')==12 and self.current_visual==12:label+=f'  COLOR X:{cx*100:.0f}% Y:{cy*100:.0f}%'
              if i==1:label+=f'  VOL CC7:{self.card2_volume}  FILTRE CC74:{self.card2_filter}'
              tx=max(4,min(frame.shape[1]-320,int(p[:,0].min())))
              ty=max(20,int(p[:,1].min())-9)
              cv2.rectangle(frame,(tx-2,ty-18),(min(frame.shape[1]-1,tx+316),ty+5),(10,25,30),-1)
              cv2.putText(frame,label,(tx,ty),cv2.FONT_HERSHEY_SIMPLEX,.48,(0,240,255),1,cv2.LINE_AA)
          self.expire_missing_cards(seen,now)
          # Mostrem la imatge original: els textos i els contorns es llegeixen correctament.
          if self.camera_window.state()=='normal':self.display(self.cam_label,cv2.cvtColor(frame,cv2.COLOR_BGR2RGB),'cam_photo')
      self.sync_mute_controls()
      now_vis=time.monotonic();frame_changed=False
      self.process_spatial_frame(zone_observations,color_observations,now_vis)
      if self.last_frame is None or self.visual_dirty or (not self.visual_paused and now_vis-self.last_visual_update>=self.visual_interval):
        t=now_vis-self.t0
        self.last_frame=self.compose_output_frame(t)
        self.visual_dirty=False
        self.last_visual_update=now_vis;frame_changed=True
      if self.visual_window.state()=='normal' and (self.preview_dirty or frame_changed):
        preview=self.card_preview_frame(self.preview_card,now_vis-self.t0) if self.preview_card is not None else self.live_preview_frame()
        if self.preview_card is not None and self.sim_card is not None and self.sim_xy is not None:
          px,py=self.tracking_point(*self.sim_xy,self.radial_preview())
          cv2.circle(preview,(px,py),14,(0,240,255),2)
          cv2.putText(preview,f'SIM T{self.sim_card+1:02d}',(max(0,min(W-110,px+18)),max(20,py)),cv2.FONT_HERSHEY_SIMPLEX,.5,(0,240,255),1)
        self.display(self.vis_label,cv2.cvtColor(preview,cv2.COLOR_BGR2RGB),'vis_photo')
        self.preview_dirty=False
      vis=self.last_frame
      if getattr(self,'projection',None) and self.projection.winfo_exists():
        self.display(self.proj_label,cv2.cvtColor(self.projector_frame(),cv2.COLOR_BGR2RGB),'proj_photo',padding=0)
      if self.recording:self.recording.write(vis)
      self.monitor_ticks+=1
      if self.monitor_ticks%4==0:
        self.update_cards_table();self.update_midi_diagnostics()
    except Exception as e:
      import traceback
      traceback.print_exc()
      self.status.set('Avís: '+str(e))
    if not self._closing:self.root.after(35,self.tick)
 def display(self,label,rgb,attr,padding=8):
    # Escalem sense modificar la mida del widget; els dos monitors queden separats.
    available_w=max(1,label.winfo_width()-padding)
    available_h=max(1,label.winfo_height()-padding)
    h,w=rgb.shape[:2]
    factor=min(available_w/w,available_h/h)
    size=(max(1,int(w*factor)),max(1,int(h*factor)))
    if size!=(w,h):rgb=cv2.resize(rgb,size,interpolation=cv2.INTER_AREA if factor<1 else cv2.INTER_LINEAR)
    photo=ImageTk.PhotoImage(Image.fromarray(rgb))
    setattr(self,attr,photo);label.config(image=photo,text='')
 def close(self):
    if not self.confirm_zone_discard():return
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
