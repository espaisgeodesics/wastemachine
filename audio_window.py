"""Operator controls for optional local audio. Worker snapshots only, no SDL calls."""
from pathlib import Path
import tkinter as tk
from tkinter import ttk

from local_audio import AudioCommand


class AudioWindow(ttk.Frame):
    def __init__(self,parent,controller):
        super().__init__(parent,padding=10)
        self.controller=controller;self.timer=None;self.lookup={}
        self.pack(fill='both',expand=True)
        ttk.Label(self,text='ÀUDIO LOCAL · prototip opcional',font=('Segoe UI',12,'bold')).pack(anchor='w')
        ttk.Label(self,text='Canals locals independents de MIDI i Sonar. Obrir un projecte no activa un dispositiu desactivat.',wraplength=850).pack(anchor='w')
        controls=ttk.Frame(self);controls.pack(fill='x',pady=8)
        for label,callback in (('ACTIVAR',controller.enable),('DESACTIVAR',controller.disable),('ATURAR ÀUDIO LOCAL',controller.stop_all),('ATURAR CAPA',self.stop_selected)):
            ttk.Button(controls,text=label,command=callback).pack(side='left',padx=3)
        self.status=tk.StringVar();ttk.Label(self,textvariable=self.status,wraplength=850).pack(anchor='w')
        self.level=tk.DoubleVar(value=controller.master*100)
        ttk.Label(self,text='Volum màster local (%)').pack(anchor='w',pady=(8,0))
        ttk.Scale(self,from_=0,to=100,variable=self.level,command=lambda value:controller.set_master(float(value)/100)).pack(fill='x')
        columns=('group','channel','source','marker','file','gain','fade')
        self.table=ttk.Treeview(self,columns=columns,show='headings',height=10,selectmode='browse')
        for key,label,width in zip(columns,('Grup','Canal local','Font','ID','Fitxer','Volum %','Fade'),(100,80,100,50,210,70,70)):
            self.table.heading(key,text=label);self.table.column(key,width=width)
        self.table.pack(fill='both',expand=True,pady=8)
        self.details=tk.StringVar();ttk.Label(self,textvariable=self.details,wraplength=850).pack(anchor='w')
        ttk.Label(self,text='Tancar el panell manté la reproducció. ATURAR ÀUDIO LOCAL no controla Sonar. Complement opcional: INSTAL_LAR_AUDIO_LOCAL.bat; després OBRIR_WASTELAND.bat. WAV PCM/OGG curts, fins a 30 s.',wraplength=850).pack(anchor='w',pady=8)
        self.bind('<Destroy>',self.destroyed,add='+');self.refresh()

    def stop_selected(self):
        rows=self.table.selection()
        if rows and rows[0] in self.lookup:
            voice=self.lookup[rows[0]]
            try:self.controller.submit(AudioCommand('stop_sound',voice.group,voice.source_id,voice.marker_id,fade_s=.2))
            except ValueError as exc:self.status.set(str(exc))

    def refresh(self):
        state=self.controller.snapshot()
        label={'disabled':'Desactivat','starting':'Activant','ready':'Actiu','error':'Error','stopping':'Aturant'}[state.state]
        self.status.set(f'{label}: {state.detail} · {len(state.voices)}/16 veus · memòria {state.cache_bytes/1048576:.1f} MiB · cua {state.queued}')
        self.lookup={str(v.slot):v for v in state.voices}
        for iid in self.table.get_children():
            if iid not in self.lookup:self.table.delete(iid)
        for iid,voice in self.lookup.items():
            values=(voice.group,voice.slot+1,voice.source_id,voice.marker_id if voice.marker_id is not None else '—',Path(voice.path).name,round(voice.gain*100),'Sí' if voice.fading else 'No')
            if self.table.exists(iid):self.table.item(iid,values=values)
            else:self.table.insert('','end',iid=iid,values=values)
        self.details.set('\n'.join(f'{kind}: {detail}' for _,kind,detail in state.log[-4:]))
        self.timer=self.after(200,self.refresh)

    def destroyed(self,event):
        if event.widget is self and self.timer is not None:self.after_cancel(self.timer);self.timer=None
