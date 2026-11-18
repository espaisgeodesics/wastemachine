"""Per-card generated visual / image / silent-video settings."""
from pathlib import Path
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from card_media import MEDIA_VISUAL,MEDIA_LABEL,VIDEOS,media_settings
from spatial_zones import image_reference


class CardMediaEditor(ttk.Frame):
    def __init__(self,window,app,names):
        super().__init__(window,padding=16);self.pack(fill='both',expand=True)
        self.app,self.window=app,window;self.index=int(app.card_id.get())-1;self.generation=app.live_kaoss.generation
        card=app.cards[self.index];settings=media_settings(card)
        self.source=tk.StringVar(value='file' if card.get('visual')==MEDIA_VISUAL else 'generated')
        self.generated=tk.StringVar(value=names[card['visual']] if card.get('visual',13)!=MEDIA_VISUAL else 'Cap')
        self.path=tk.StringVar(value=settings['media_path']);self.loop=tk.BooleanVar(value=settings['media_loop'])
        self.priority=tk.IntVar(value=settings['media_priority'])
        self.fade_in=tk.StringVar(value=str(settings['media_fade_in_s']));self.fade_out=tk.StringVar(value=str(settings['media_fade_out_s']))
        ttk.Label(self,text=f'Visual · Targeta {self.index+1:02d}',font=('Segoe UI',15,'bold')).pack(anchor='w',pady=(0,12))
        ttk.Radiobutton(self,text='Visual generat',variable=self.source,value='generated').pack(anchor='w')
        values=['Cap']+[name for name in names if name not in ('Cap',MEDIA_LABEL)]
        ttk.Combobox(self,textvariable=self.generated,values=values,state='readonly').pack(fill='x',pady=5)
        ttk.Radiobutton(self,text='Fitxer d’imatge o vídeo',variable=self.source,value='file').pack(anchor='w',pady=(12,0))
        ttk.Entry(self,textvariable=self.path,state='readonly').pack(fill='x',pady=5)
        ttk.Button(self,text='Triar imatge / vídeo…',command=self.choose).pack(fill='x',pady=4)
        ttk.Checkbutton(self,text='Repetir vídeo en bucle',variable=self.loop).pack(anchor='w',pady=4)
        for title,variable,low,high in [('Fade in (s)',self.fade_in,0,10),('Fade out (s)',self.fade_out,0,10),('Prioritat',self.priority,1,1000)]:
            row=ttk.Frame(self);row.pack(fill='x',pady=4);ttk.Label(row,text=title).pack(side='left')
            ttk.Spinbox(row,textvariable=variable,from_=low,to=high,increment=.1 if high==10 else 1,width=8).pack(side='right')
        ttk.Label(self,text='La targeta activa el fitxer; en retirar-la fa fade out. Les imatges es mostren amb la seva proporció.\nVídeo sense pista d’àudio integrada: el so local es pot activar des de zones. La lectura del vídeo depèn del còdec disponible.',wraplength=500).pack(anchor='w',pady=12)
        self.status=tk.StringVar(value='Aplica a la targeta i desa el projecte per conservar el fitxer i les transicions.')
        ttk.Label(self,textvariable=self.status,wraplength=500).pack(fill='x',pady=8)
        ttk.Button(self,text='APLICAR A LA TARGETA',command=self.apply,style='Accent.TButton').pack(fill='x',pady=5)

    def choose(self):
        path=filedialog.askopenfilename(parent=self.window,filetypes=[('Imatges i vídeos','*.png *.jpg *.jpeg *.bmp *.webp *.mp4 *.avi *.mov *.mkv *.webm *.m4v'),('Tots els fitxers','*.*')])
        if not path:return
        project=self.app.zone_project_path()
        self.path.set(image_reference(path,project) if project else str(Path(path).resolve()))
        self.source.set('file')

    def apply(self):
        if self.generation!=self.app.live_kaoss.generation or self.app.card_id.get()!=f'{self.index+1:02d}':
            messagebox.showwarning('Visual de targeta','La targeta o el projecte ha canviat. Torna a obrir la configuració.',parent=self.window);return False
        previous=getattr(self.app,'media_draft',None);visual=self.app.visual.get()
        try:
            settings=media_settings(dict(media_path=self.path.get(),media_loop=self.loop.get(),media_priority=int(self.priority.get()),media_fade_in_s=float(self.fade_in.get().replace(',','.')),media_fade_out_s=float(self.fade_out.get().replace(',','.'))),required=self.source.get()=='file')
            self.app.media_draft=settings;self.app.visual.set(MEDIA_LABEL if self.source.get()=='file' else self.generated.get())
            if not self.app.apply_card():self.app.media_draft=previous;self.app.visual.set(visual);return False
            self.status.set('Visual aplicat a la targeta. Desa el projecte.');return True
        except (ValueError,tk.TclError) as exc:
            self.app.media_draft=previous;self.app.visual.set(visual)
            messagebox.showerror('Visual de targeta',str(exc),parent=self.window);return False
