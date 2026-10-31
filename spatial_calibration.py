"""Four fixed floor references selected on an unmirrored camera snapshot."""
import time
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
from spatial_zones import Calibration

REFERENCES = ('NORD', 'EST', 'SUD', 'OEST')


class CalibrationEditor:
    def __init__(self, window, get_frame, get_context, get_calibration, on_apply):
        self.window=window;self.get_frame=get_frame;self.get_context=get_context
        self.get_calibration=get_calibration;self.on_apply=on_apply
        self.frame=None;self.stamp=None;self.context=None;self.frozen=False
        self.points=[None]*4;self.selected=tk.IntVar(value=0);self.photo=None;self.bounds=None
        self.notice=tk.StringVar(value='Obre la càmera i prem CONGELAR IMATGE.')
        ttk.Label(window,text='Marca quatre punts FIXOS del perímetre del terra: NORD, EST, SUD i OEST.\n'
                  'La càmera ha de quedar immòbil. Imatge original, sense mirall. Els punts no són les posicions de la targeta.',wraplength=850).pack(fill='x',padx=10,pady=8)
        controls=ttk.Frame(window);controls.pack(fill='x',padx=10)
        ttk.Button(controls,text='CONGELAR IMATGE',command=self.freeze).pack(side='left',padx=3)
        ttk.Button(controls,text='REPETIR CAPTURA',command=self.restart).pack(side='left',padx=3)
        for i,name in enumerate(REFERENCES):
            ttk.Radiobutton(controls,text=name,variable=self.selected,value=i,command=self.draw).pack(side='left',padx=7)
        self.canvas=tk.Canvas(window,bg='#101519',highlightthickness=0,width=800,height=450)
        self.canvas.pack(fill='both',expand=True,padx=10,pady=8)
        self.canvas.bind('<Configure>',lambda event:self.draw())
        self.canvas.bind('<Button-1>',self.click)
        ttk.Label(window,textvariable=self.notice,wraplength=850).pack(fill='x',padx=10,pady=4)
        footer=ttk.Frame(window);footer.pack(fill='x',padx=10,pady=8)
        ttk.Button(footer,text='APLICAR CALIBRACIÓ',command=self.apply).pack(side='left',padx=3)
        ttk.Label(footer,text='Després desa el projecte per conservar-la.').pack(side='left',padx=10)
        self.refresh()

    def restart(self):
        self.frozen=False;self.frame=None;self.stamp=None;self.context=None
        self.points=[None]*4;self.selected.set(0);self.bounds=None
        self.notice.set('Captura en directe. Prem CONGELAR IMATGE abans de marcar els punts.')
        self.refresh();self.draw()

    def refresh(self):
        if self.frozen:return
        frame,stamp=self.get_frame()
        if frame is None or time.monotonic()-stamp>1:
            self.frame=None;self.bounds=None;self.draw();return
        if stamp!=self.stamp:
            self.frame=frame;self.stamp=stamp;self.context=self.get_context();self.draw()

    def freeze(self):
        frame,stamp=self.get_frame()
        if frame is None or time.monotonic()-stamp>1:
            self.notice.set('No hi ha una imatge recent. Obre la càmera i torna-ho a provar.');return False
        self.frame=frame.copy();self.stamp=stamp;self.context=self.get_context();self.frozen=True
        saved=self.get_calibration()
        self.points=list(saved.camera_points) if saved else [None]*4
        self.selected.set(0);self.notice.set('Imatge congelada. Marca NORD, EST, SUD i OEST; pots corregir cada punt seleccionant-ne el nom.')
        self.draw();return True

    def click(self,event):
        if not self.frozen or self.bounds is None:
            self.notice.set('Primer congela una imatge de la càmera.');return
        x,y,width,height=self.bounds
        if not (x<=event.x<=x+width and y<=event.y<=y+height):return
        index=self.selected.get();self.points[index]=((event.x-x)/width,(event.y-y)/height)
        self.selected.set(min(3,index+1));self.draw()
        self.notice.set('Punts marcats: '+str(sum(p is not None for p in self.points))+'/4. '+
                        ('Prem APLICAR CALIBRACIÓ.' if all(p is not None for p in self.points) else 'Següent: '+REFERENCES[self.selected.get()]))

    def apply(self):
        if not self.frozen or any(point is None for point in self.points):
            self.notice.set('Cal congelar la imatge i marcar els quatre punts.');return False
        if self.context!=self.get_context():
            self.notice.set('Ha canviat el projecte o la càmera. Repeteix la captura.');return False
        try:calibration=Calibration(tuple(self.points))
        except ValueError:
            self.notice.set('Punts no vàlids: han de formar un perímetre sense creuaments i ben separat. Revisa NORD, EST, SUD i OEST.');return False
        if self.on_apply(calibration) is False:return False
        self.notice.set('Calibració aplicada. Comprova la targeta al mapa i desa el projecte. Si mous la càmera, torna a calibrar.')
        return True

    def draw(self):
        self.canvas.delete('all');self.bounds=None
        if self.frame is None:
            self.canvas.create_text(max(100,self.canvas.winfo_width()/2),80,text='Sense imatge recent de càmera',fill='white');return
        height,width=self.frame.shape[:2]
        cw=max(1,self.canvas.winfo_width());ch=max(1,self.canvas.winfo_height())
        factor=min(cw/width,ch/height);dw=max(1,int(width*factor));dh=max(1,int(height*factor))
        x=(cw-dw)/2;y=(ch-dh)/2;self.bounds=(x,y,dw,dh)
        self.photo=ImageTk.PhotoImage(Image.fromarray(self.frame[:,:,::-1]).resize((dw,dh),Image.Resampling.BILINEAR))
        self.canvas.create_image(x,y,image=self.photo,anchor='nw')
        if not self.frozen:return
        coords=[(x+p[0]*dw,y+p[1]*dh) if p is not None else None for p in self.points]
        for i,point in enumerate(coords):
            following=coords[(i+1)%4]
            if point and following:self.canvas.create_line(*point,*following,fill='#ffbb55',width=2)
            if point:
                px,py=point;color='#ffff77' if i==self.selected.get() else '#55ffee'
                self.canvas.create_oval(px-6,py-6,px+6,py+6,outline=color,width=3)
                self.canvas.create_text(min(cw-30,max(30,px)),max(12,py-16),text=REFERENCES[i],fill=color,font=('Segoe UI',11,'bold'))
