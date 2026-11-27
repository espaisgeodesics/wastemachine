"""Operator-only spatial map. No marker, grid or label is sent to projection."""
from functools import lru_cache
import math
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

NO_VISUAL = 13
MEDIA_VISUAL = 14
SURFACES = {'Cercle': 'circle', 'Quadrat': 'square', 'Rectangle': 'rectangle'}


def visual_index(value):
    if value is None or value == -1:return NO_VISUAL
    if type(value) is not int or not 0 <= value <= MEDIA_VISUAL:
        raise ValueError('Visual assignat no vàlid')
    return value


def assigned_visuals(cards, active, zone_function):
    return sorted({visual_index(cards[i].get('visual',NO_VISUAL)) for i in active
                   if cards[i].get('function') not in ('Cap acció',zone_function)
                   and visual_index(cards[i].get('visual',NO_VISUAL)) not in (NO_VISUAL,MEDIA_VISUAL)})


def mix_frames(layers, width, height):
    if not layers:return np.zeros((height,width,3),np.uint8)
    if len(layers)==1:return layers[0].copy()
    remaining=np.ones((height,width,3),np.float32)
    gain=1/math.sqrt(len(layers))
    for layer in layers:remaining*=1-layer.astype(np.float32)*(gain/255)
    return np.clip((1-remaining)*255,0,255).astype(np.uint8)


@lru_cache(maxsize=4)
def font(size):
    for name in ('C:/Windows/Fonts/segoeui.ttf','DejaVuSans.ttf'):
        try:return ImageFont.truetype(name,size)
        except OSError:pass
    return ImageFont.load_default()


def bounds(width,height,surface,panel_width=0,aspect_ratio=None):
    available_h=max(1,height-96)
    available_w=max(1,width-64-panel_width)
    ratio=(aspect_ratio or width/height) if surface=='rectangle' else 1
    h=min(available_h,available_w/ratio);w=h*ratio
    return ((width-panel_width-w)/2,54+(available_h-h)/2,(width-panel_width+w)/2,54+(available_h+h)/2)


def floor_point(position, calibration):
    point=calibration.project(position) if calibration is not None else position
    if point is None or any(not math.isfinite(v) for v in point):return None
    return point if all(0<=v<=1 for v in point) else None


def map_frame(content_bgr,cards,active,trails,config,surface='circle',color_bgr=None,now=0,icons=None,music_layers=None):
    if config.calibration is not None:surface=config.calibration.shape
    if surface not in SURFACES.values():raise ValueError('Forma del mapa no vàlida')
    height,width=content_bgr.shape[:2]
    canvas=Image.new('RGB',(width,height),'#0b1224')
    draw=ImageDraw.Draw(canvas)
    box=bounds(width,height,surface,180 if (active or music_layers) else 0,getattr(config.calibration,'aspect_ratio',None));left,top,right,bottom=box
    w,h=right-left,bottom-top
    shape='ellipse' if surface=='circle' else 'rectangle'
    rgb_color=tuple(int(v) for v in color_bgr[::-1]) if color_bgr is not None else (69,212,210)
    outer=(left-10,top-10,right+10,bottom+10)
    getattr(draw,shape)(outer,outline=rgb_color,width=8 if color_bgr is not None else 2)
    mask=Image.new('L',(width,height));getattr(ImageDraw.Draw(mask),shape)(box,fill=255)
    content=ImageOps.contain(Image.fromarray(np.ascontiguousarray(content_bgr[:,:,::-1])),(max(1,round(w)),max(1,round(h))))
    inner=Image.new('RGB',(width,height),'black');inner.paste(content,(round(left+(w-content.width)/2),round(top+(h-content.height)/2)))
    canvas.paste(inner,(0,0),mask)
    overlay=Image.new('RGBA',(width,height));zones=ImageDraw.Draw(overlay)
    for zone in config.zones:
        if not zone.enabled:continue
        color=(69,212,210,95) if zone.audio_path else (155,140,255,95)
        for row,col in zone.cells:
            cell=(left+col*w/config.grid.columns,top+row*h/config.grid.rows,
                  left+(col+1)*w/config.grid.columns,top+(row+1)*h/config.grid.rows)
            zones.rectangle(cell,outline=color,width=1)
    alpha=np.asarray(overlay.getchannel('A')).copy()
    alpha[np.asarray(mask)==0]=0
    overlay.putalpha(Image.fromarray(alpha))
    canvas=Image.alpha_composite(canvas.convert('RGBA'),overlay).convert('RGB');draw=ImageDraw.Draw(canvas)
    if music_layers:
        canvas=draw_music_layers(canvas,box,mask,music_layers);draw=ImageDraw.Draw(canvas)
    draw.text((12,7),'MAPA DE L’ESPAI · '+next(k for k,v in SURFACES.items() if v==surface),fill='#f5f7ff',font=font(13))
    calibration=config.calibration
    caption='Coordenades calibrades' if calibration is not None else 'Coordenades de càmera · sense calibrar'
    draw.text((12,27),caption,fill='#a8bad5',font=font(10))
    colors=((69,212,210),(155,140,255),(247,194,122),(128,197,247))
    outside=0
    for index,position in sorted(active.items()):
        point=floor_point(position[:2],calibration)
        if point is None:outside+=1;continue
        x,y=point;px,py=left+x*w,top+y*h
        inside=surface!='circle' or math.hypot(x-.5,y-.5)<=.5
        if not inside:outside+=1
        color=colors[index%len(colors)] if inside else (130,140,155)
        points=[]
        for stamp,tx,ty in trails.get(index,()):
            if now-stamp>2.5:continue
            p=floor_point((tx,ty),calibration)
            if p is not None:points.append((left+p[0]*w,top+p[1]*h))
        if len(points)>1:draw.line(points,fill=color,width=2)
        visual=visual_index(cards[index].get('visual',NO_VISUAL))
        icon=(icons or {}).get(visual)
        if icon is not None and inside:
            thumbnail=ImageOps.contain(Image.fromarray(np.ascontiguousarray(icon[:,:,::-1])),(28,28))
            canvas.paste(thumbnail,(round(px)-thumbnail.width//2,round(py)-thumbnail.height//2))
            draw=ImageDraw.Draw(canvas)
            draw.rectangle((px-15,py-15,px+15,py+15),outline=color,width=2)
        else:
            draw.ellipse((px-7,py-7,px+7,py+7),fill='#0b1224',outline=color,width=2)
        angle=position[2]*math.tau
        draw.line((px,py,px+19*math.cos(angle),py+19*math.sin(angle)),fill=color,width=2)
        # Full function descriptions belong in the legend, not over the map.
        label=f'T{index+1:02d}' + (' · fora' if not inside else '')
        tx=min(max(4,round(px+18)),max(4,width-round(draw.textlength(label,font=font(10)))-5))
        ty=min(max(46,round(py-20)),height-38)
        text_box=draw.textbbox((tx,ty),label,font=font(10))
        draw.rectangle((text_box[0]-3,text_box[1]-2,text_box[2]+3,text_box[3]+2),fill='#0b1224')
        draw.text((tx,ty),label,fill=color,font=font(10))
    draw_card_legend(draw, width, height, cards, active, music_layers or [])
    footer=f'{len(active)} targetes actives · Marques només aquí'
    if outside:footer+=f' · {outside} fora del mapa'
    draw.text((12,height-20),footer,fill='#a8bad5',font=font(10))
    return np.asarray(canvas)[:,:,::-1].copy()


def map_pointer(x,y,widget_width,widget_height,frame_width,frame_height,surface,calibration=None,panel_width=0):
    if calibration is not None:surface=calibration.shape
    factor=min(max(1,widget_width-8)/frame_width,max(1,widget_height-8)/frame_height)
    image_w=max(1,int(frame_width*factor));image_h=max(1,int(frame_height*factor))
    frame_x=(x-(widget_width-image_w)/2)/image_w*frame_width
    frame_y=(y-(widget_height-image_h)/2)/image_h*frame_height
    left,top,right,bottom=bounds(frame_width,frame_height,surface,panel_width,getattr(calibration,'aspect_ratio',None))
    point=((frame_x-left)/(right-left),(frame_y-top)/(bottom-top))
    if not all(0<=value<=1 for value in point):return None
    if surface=='circle' and math.hypot(point[0]-.5,point[1]-.5)>.5:return None
    result=calibration.unproject(point) if calibration is not None else point
    return result if result is not None and all(0<=value<=1 for value in result) else None


def draw_music_layers(canvas,box,mask,layers):
    from atmo_music import note_label
    width,height=canvas.size;left,top,right,bottom=box;w,h=right-left,bottom-top
    yy,xx=np.ogrid[:height,:width]
    x=(xx-left)/w;y=(yy-top)/h
    theta=(np.arctan2(.5-y,x-.5)+math.tau)%math.tau
    radial_sector=((theta+math.pi/8)//(math.pi/4)).astype(int)%8
    radius=np.sqrt((x-.5)**2+(y-.5)**2)*2
    radial_ring=np.where(radius<1/3,0,np.where(radius<2/3,1,2))
    grid_col=np.clip(((xx-left)/w*8).astype(int),0,7)
    grid_row=np.clip(((yy-top)/h*3).astype(int),0,2)
    palette=((69,212,210),(155,140,255),(247,194,122),(128,197,247))
    overlay=Image.new('RGBA',canvas.size);draw=ImageDraw.Draw(overlay)
    drawn_layouts=set()
    for layer in layers:
        color=palette[layer['id']%len(palette)]
        cell=layer.get('cell')
        if cell is not None:
            sector,ring=cell
            selected=((grid_col==sector)&(grid_row==ring)) if layer['layout']=='grid' else ((radial_sector==sector)&(radial_ring==ring))
            fill=np.zeros((height,width,4),np.uint8);fill[selected]=(color[0],color[1],color[2],60 if layer.get('confirmed') else 28)
            overlay=Image.alpha_composite(overlay,Image.fromarray(fill));draw=ImageDraw.Draw(overlay)
        if layer['layout'] in drawn_layouts:continue
        drawn_layouts.add(layer['layout'])
        line=(168,186,213,65)
        if layer['layout']=='grid':
            for col in range(1,8):draw.line((left+col*w/8,top,left+col*w/8,bottom),fill=line,width=1)
            for row in range(1,3):draw.line((left,top+row*h/3,right,top+row*h/3),fill=line,width=1)
        else:
            for fraction in (1/3,2/3):
                draw.ellipse((left+w*(1-fraction)/2,top+h*(1-fraction)/2,left+w*(1+fraction)/2,top+h*(1+fraction)/2),outline=line,width=1)
            for sector in range(8):
                angle=(sector+.5)*math.pi/4
                draw.line(((left+right)/2,(top+bottom)/2,(left+right)/2+w*math.cos(angle),(top+bottom)/2-h*math.sin(angle)),fill=line,width=1)
    alpha=np.asarray(overlay.getchannel('A')).copy();alpha[np.asarray(mask)==0]=0;overlay.putalpha(Image.fromarray(alpha))
    canvas=Image.alpha_composite(canvas.convert('RGBA'),overlay).convert('RGB');draw=ImageDraw.Draw(canvas)
    return canvas


def draw_card_legend(draw, width, height, cards, active, music_layers):
    """One colour per card; keep note/activity details outside the spatial map."""
    palette=((69,212,210),(155,140,255),(247,194,122),(128,197,247))
    layers={layer['id']:layer for layer in music_layers}
    ids=sorted(set(active)|set(layers))
    if not ids:return
    x=width-174;y=56
    draw.text((x,y),'TARGETES I FUNCIONS',fill='#a8bad5',font=font(10));y+=22
    for position,index in enumerate(ids):
        layer=layers.get(index)
        details=layer['lines'][:3] if layer else [str(cards[index].get('function','Cap acció'))]
        if y+30+12*len(details)>height-25:
            draw.text((x,y),f'+ {len(ids)-position} targetes actives',fill='#a8bad5',font=font(10));break
        color=palette[index%len(palette)]
        title=f'T{index+1:02d} · '+(layer['kind'] if layer else 'Activa')
        draw.text((x,y),title,fill=color,font=font(11));y+=17
        for line in details:
            # Split descriptions by measured width rather than cutting words.
            words=str(line).split();text=''
            for word in words:
                candidate=(text+' '+word).strip()
                if draw.textlength(candidate,font=font(9))>166 and text:
                    draw.text((x,y),text,fill='#d2deee',font=font(9));y+=12;text=word
                else:text=candidate
            draw.text((x,y),text,fill='#d2deee',font=font(9));y+=12
        y+=12
