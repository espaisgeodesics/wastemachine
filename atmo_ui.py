"""Presentation helpers. No media, projection or MIDI behaviour lives here."""
import math
import tkinter as tk
from tkinter import ttk
from functools import lru_cache
from PIL import Image,ImageTk,ImageDraw,ImageFilter

def leaf_motif(draw, origin, length, angle, fill, vein, width=1):
    """A tapered leaf in local coordinates; never draws on media/projector canvases."""
    ox,oy=origin;ux,uy=math.cos(angle),math.sin(angle);vx,vy=-uy,ux
    def point(t,side):
        breadth=math.sin(math.pi*t)*length*.22*side
        return ox+ux*length*t+vx*breadth,oy+uy*length*t+vy*breadth
    outline=[point(i/24,1) for i in range(25)]+[point(i/24,-1) for i in range(24,-1,-1)]
    draw.polygon(outline,fill=fill)
    draw.line((origin,point(1,0)),fill=vein,width=width)
    for t in (.28,.45,.62,.77):
        for side in (-1,1):draw.line((point(t,0),point(min(.96,t+.12),side*.75)),fill=vein,width=width)


@lru_cache(maxsize=8)
def atmosphere_art(width,height):
    from atmo_runtime import BG
    image=Image.new('RGBA',(width,height),BG)
    glow=Image.new('RGBA',image.size)
    draw=ImageDraw.Draw(glow)
    draw.ellipse((width*.45,-height,width*.98,height*1.7),fill=(60,151,130,100))
    draw.ellipse((width*.76,-height*.4,width*1.15,height*1.8),fill=(73,126,171,80))
    draw.ellipse((width*.58,-height*.5,width*.85,height*1.3),fill=(149,177,95,55))
    image=Image.alpha_composite(image,glow.filter(ImageFilter.GaussianBlur(max(8,height*.28))))
    line=ImageDraw.Draw(image)
    for offset,color in ((0,'#376357'),(15,'#2a5367')):
        points=[(width*(.44+.7*i/120),height*(.55+.24*math.sin(i/120*math.tau-.8))+offset) for i in range(121)]
        line.line(points,fill=color,width=1,joint='curve')
    # Leaves inhabit the right edge; the title and subtitle stay on a quiet field.
    for x,y,size,angle in ((.76,.90,.65,-1.0),(.86,1.20,.85,-1.8),(.98,.95,.9,-2.1)):
        leaf_motif(line,(width*x,height*y),height*size,angle,'#254f43','#548268')
    return image.convert('RGB')


@lru_cache(maxsize=4)
def forest_overlay(width,height):
    """Quiet botanical border for workspace artwork, clear in the central work area."""
    overlay=Image.new('RGBA',(width,height))
    draw=ImageDraw.Draw(overlay)
    size=min(width,height)
    for side in (-1,1):
        ox=width*.02 if side==1 else width*.98
        for i in range(6):
            y=height*(.25+i*.15)
            length=size*(.17+.025*(i%3))
            leaf_motif(draw,(ox,y),length,-.9 if side==1 else -2.2,
                       (40,91,60,115),(139,177,111,90),max(1,round(size/600)))
    return overlay


def draw_banner(app,event):
    from atmo_runtime import BG,TEXT,CYAN,PURPLE,FONT,LEAF
    canvas=app.banner_canvas;width=max(1,event.width);height=84
    canvas.configure(height=height,bg=BG);canvas.delete('all')
    app.banner_photo=ImageTk.PhotoImage(atmosphere_art(width,height),master=canvas)
    canvas.create_image(0,0,image=app.banner_photo,anchor='nw')
    canvas.create_text(22,26,anchor='w',text='ATMO ESFERA FX',fill=TEXT,font=(FONT,23,'bold'))
    canvas.create_text(24,58,anchor='w',text='Atmosfera viva · L’espai es converteix en instrument',fill=CYAN,font=(FONT,10))
    if width>850:canvas.create_text(width-24,28,anchor='e',text='ESPAI  ·  SO  ·  IMATGE',fill=LEAF,font=(FONT,10,'bold'))


def scrollable_form(parent,padding=12):
    from atmo_runtime import BG
    holder=ttk.Frame(parent);holder.pack(fill='both',expand=True)
    canvas=tk.Canvas(holder,bg=BG,highlightthickness=0)
    bar=ttk.Scrollbar(holder,orient='vertical',command=canvas.yview)
    bar.pack(side='right',fill='y');canvas.pack(side='left',fill='both',expand=True)
    canvas.configure(yscrollcommand=bar.set)
    body=ttk.Frame(canvas,padding=padding);item=canvas.create_window((0,0),window=body,anchor='nw')
    body.bind('<Configure>',lambda event:canvas.configure(scrollregion=canvas.bbox('all')))
    canvas.bind('<Configure>',lambda event:canvas.itemconfigure(item,width=event.width))
    # Bind only descendants of this form, not every window in the application.
    def wheel(event):
        canvas.yview_scroll(-1 if getattr(event,'num',0)==4 or getattr(event,'delta',0)>0 else 1,'units')
        return 'break'
    def bind_children(widget):
        for child in widget.winfo_children():
            child.bind('<MouseWheel>',wheel,add='+');child.bind('<Button-4>',wheel,add='+');child.bind('<Button-5>',wheel,add='+')
            bind_children(child)
    body.after_idle(lambda:bind_children(body) if body.winfo_exists() else None)
    body.atmo_canvas=canvas
    return body


def wrap_controls(frame):
    state={'width':None,'busy':False}
    def arrange(event=None):
        if state['busy'] or not frame.winfo_exists():return
        width=frame.winfo_width()
        if width<2 or state['width']==width:return
        state['busy']=True;state['width']=width
        try:
            children=frame.winfo_children()
            for widget in children:
                if widget.winfo_manager()=='pack':widget.pack_forget()
                else:widget.grid_forget()
            x=0;row=0;column=0
            for widget in children:
                needed=widget.winfo_reqwidth()+10
                if x and x+needed>width:row+=1;column=0;x=0
                widget.grid(row=row,column=column,sticky='w',padx=4,pady=4)
                x+=needed;column+=1
        finally:state['busy']=False
    frame.bind('<Configure>',arrange,add='+');frame.after_idle(arrange)


def build_workspace(app):
    from pathlib import Path
    from atmo_project_background import ProjectBackground
    names={'Joc':'joc','Música':'musica','Exposició':'exposicio',
           'Instal·lació immersiva':'immersiva'}
    mode=getattr(app,'atmo_experience_mode','Instal·lació immersiva')
    image=Path(__file__).resolve().parent/'atmo_assets'/('atmo_'+names.get(mode,'immersiva')+'.png')
    area=ProjectBackground(app.root,image,with_panel=False)
    area.pack(fill='both',expand=True,pady=(8,0))
    return area


def install_menu_bar(app):
    """Reuse every existing menu command in a themed, keyboard accessible bar."""
    menu_name=app.root.cget('menu')
    if not menu_name:return
    menu=app.root.nametowidget(menu_name)
    bar=ttk.Frame(app.root,style='Card.TFrame')
    bar.pack(fill='x',before=app.banner_canvas)
    app.root.configure(menu='')
    for index in range((menu.index('end') or 0)+1):
        if menu.type(index)!='cascade':continue
        title=menu.entrycget(index,'label');submenu=menu.entrycget(index,'menu')
        if title=='Àudio':continue
        button=ttk.Menubutton(bar,text=title,menu=submenu,underline=0,takefocus=True)
        button.pack(side='left',padx=3,pady=3)
        def post(event,widget=button,path=submenu):
            widget.focus_set()
            widget.tk.call(path,'post',widget.winfo_rootx(),widget.winfo_rooty()+widget.winfo_height())
            return 'break'
        if title:app.root.bind('<Alt-'+title[0].lower()+'>',post,add='+')
    app.atmo_menu_bar=bar


def wrap_card_text(container):
    """Keep long experience names and entry actions within each approved artwork card."""
    state={'width':None}
    def reflow(event=None):
        width=container.winfo_width()
        if width<2 or width==state['width']:return
        state['width']=width
        for child in container.winfo_children():
            if 'wraplength' in child.keys():child.configure(wraplength=max(80,width-34),justify='center')
    for child in container.winfo_children():
        if 'wraplength' in child.keys():child.configure(wraplength=140,justify='center')
    container.bind('<Configure>',reflow,add='+')
