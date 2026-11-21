"""Asynchronous image/video decoding and frame-independent media fades."""
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from threading import Condition, Thread
import math
import time
import numpy as np
from PIL import Image, ImageOps

MEDIA_VISUAL=14
MEDIA_LABEL='Imatge / Vídeo'
IMAGES={'.png','.jpg','.jpeg','.bmp','.webp'}
VIDEOS={'.mp4','.avi','.mov','.mkv','.webm','.m4v'}


def media_settings(card,required=False):
    path=card.get('media_path','') or ''
    if not isinstance(path,str):raise ValueError('Ruta d’imatge o vídeo no vàlida')
    if required and not path:raise ValueError('Tria un fitxer d’imatge o vídeo a Configurar funció.')
    if path and Path(path).suffix.lower() not in IMAGES|VIDEOS:raise ValueError('Format d’imatge o vídeo no admès')
    result=dict(media_path=path,media_loop=card.get('media_loop',True),media_priority=card.get('media_priority',10),
                media_fade_in_s=card.get('media_fade_in_s',.5),media_fade_out_s=card.get('media_fade_out_s',1.))
    if type(result['media_loop']) is not bool:raise ValueError('Bucle de vídeo no vàlid')
    if type(result['media_priority']) is not int or not 1<=result['media_priority']<=1000:raise ValueError('Prioritat de mitjà: 1–1000')
    for key in ('media_fade_in_s','media_fade_out_s'):
        value=result[key]
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not 0<=value<=10:
            raise ValueError('Fade d’imatge/vídeo: 0–10 segons')
    return result


def rebase_card_media(cards,old_project,new_project):
    result=deepcopy(cards)
    parent=Path(new_project).resolve().parent
    for card in result:
        reference=card.get('media_path')
        if not reference:continue
        path=Path(reference)
        if not path.is_absolute():
            if old_project is None:raise ValueError('Falta el projecte d’origen per resoldre el fitxer de la targeta')
            path=Path(old_project).resolve().parent/path
        path=path.resolve()
        try:card['media_path']=path.relative_to(parent).as_posix()
        except ValueError:card['media_path']=str(path)
    return result


def fit_frame(frame,width,height):
    image=Image.fromarray(np.ascontiguousarray(frame[:,:,::-1]))
    scale=min(max(1,width)/image.width,max(1,height)/image.height)
    image=image.resize((max(1,round(image.width*scale)),max(1,round(image.height*scale))),Image.Resampling.LANCZOS)
    result=Image.new('RGB',(width,height),'black')
    result.paste(image,((width-image.width)//2,(height-image.height)//2))
    return np.asarray(result)[:,:,::-1].copy()


class MediaDecoder:
    def __init__(self,capture_factory=None):
        self.condition=Condition();self.generation=0;self.key=None;self.image=None;self.error='';self.revision=0
        self.closed=False;self.paused=False;self.thread=None;self.capture_factory=capture_factory

    def request(self,key):
        with self.condition:
            if self.closed or key==self.key:return
            self.generation+=1;self.key=key;self.image=None;self.error='';self.revision+=1
            if key is not None and self.thread is None:
                self.thread=Thread(target=self._run,name='atmo-card-media',daemon=True);self.thread.start()
            self.condition.notify_all()

    def snapshot(self):
        with self.condition:return self.image,self.error,self.revision

    def set_paused(self,paused):
        with self.condition:self.paused=bool(paused);self.condition.notify_all()

    def close(self):
        with self.condition:self.closed=True;self.condition.notify_all();thread=self.thread
        if thread is not None:thread.join(.5)

    def _capture(self,path):
        if self.capture_factory is not None:return self.capture_factory(path)
        import cv2
        return cv2.VideoCapture(path)

    def _run(self):
        capture=None;loaded=-1;is_image=False;fps=25.;due=0
        try:
            while True:
                with self.condition:
                    if self.closed:break
                    key,generation=self.key,self.generation
                    if key is None or (loaded==generation and is_image):
                        if capture is not None:capture.release();capture=None
                        self.condition.wait(.05);continue
                    if self.paused and loaded==generation:
                        due=time.monotonic();self.condition.wait(.03);continue
                    if loaded==generation and due>time.monotonic():
                        self.condition.wait(min(.1,due-time.monotonic()));continue
                try:
                    if loaded!=generation:
                        if capture is not None:capture.release();capture=None
                        path,loop,identity=key;loaded=generation;is_image=Path(path).suffix.lower() in IMAGES
                        if is_image:
                            with Image.open(path) as source:
                                image=ImageOps.exif_transpose(source).convert('RGB');image.thumbnail((1920,1080))
                                frame=np.asarray(image)[:,:,::-1].copy()
                        else:
                            capture=self._capture(path)
                            if not capture.isOpened():raise ValueError('No es pot obrir el vídeo. Comprova el fitxer i el còdec.')
                            fps=float(capture.get(5));fps=fps if math.isfinite(fps) and 1<=fps<=120 else 25.
                            ok,frame=capture.read()
                            if not ok:raise ValueError('No es pot llegir el primer fotograma del vídeo')
                    else:
                        ok,frame=capture.read()
                        if not ok:
                            if key[1]:
                                capture.set(1,0);ok,frame=capture.read()
                                if not ok:raise ValueError('No es pot reiniciar el vídeo')
                            else:
                                is_image=True;continue
                    if frame.shape[1]>1920 or frame.shape[0]>1080:frame=fit_frame(frame,1920,1080)
                    with self.condition:
                        if generation==self.generation and key==self.key:self.image=frame.copy();self.revision+=1
                    due=time.monotonic()+1/fps
                except Exception as exc:
                    if capture is not None:capture.release();capture=None
                    with self.condition:
                        if generation==self.generation:self.error=str(exc);self.revision+=1
                    is_image=True
        finally:
            if capture is not None:capture.release()


class CardMediaPlayer:
    def __init__(self,decoder=None,clock=time.monotonic):
        self.decoder=decoder or MediaDecoder();self.clock=clock
        self.key=None;self.settings=None;self.entry_start=None;self.tail=None

    def request(self,key,settings=None):
        now=self.clock()
        if key==self.key:
            if settings is not None:self.settings=settings
            return
        texture,opacity=self._layer(1280,720,now)
        duration=self.settings['media_fade_out_s'] if self.settings is not None else (self.tail[3] if self.tail else 0)
        self.tail=(texture,opacity,now,duration) if texture is not None and opacity>0 and duration>0 else None
        self.key=key;self.settings=settings;self.entry_start=None
        self.decoder.request(key)

    def _layer(self,width,height,now):
        layers=[]
        if self.tail is not None:
            texture,start,when,duration=self.tail
            opacity=start*max(0,1-(now-when)/duration)
            if opacity>0:layers.append((fit_frame(texture,width,height),opacity))
            else:self.tail=None
        texture,_,_=self.decoder.snapshot()
        if self.key is not None and texture is not None:
            if self.entry_start is None:self.entry_start=now
            duration=self.settings['media_fade_in_s']
            opacity=min(1,max(0,(now-self.entry_start)/duration)) if duration else 1
            if opacity>0:layers.append((fit_frame(texture,width,height),opacity))
        if not layers:return None,0.
        total=sum(alpha for _,alpha in layers)
        image=sum(frame.astype(np.float32)*alpha for frame,alpha in layers)/total
        return np.clip(image,0,255).astype(np.uint8),min(1,total)

    def apply(self,base):
        height,width=base.shape[:2];image,opacity=self._layer(width,height,self.clock())
        if image is None:return base
        return np.clip(base.astype(np.float32)*(1-opacity)+image.astype(np.float32)*opacity,0,255).astype(np.uint8)

    def reset(self):
        self.key=None;self.settings=None;self.entry_start=None;self.tail=None
        self.decoder.request(None)

    def close(self):self.decoder.close()

    def needs_update(self):
        now=self.clock()
        return self.tail is not None or (self.key is not None and (self.entry_start is None or now-self.entry_start<self.settings['media_fade_in_s']))
