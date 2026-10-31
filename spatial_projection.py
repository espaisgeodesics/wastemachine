"""Phase 3: bounded image cache and confirmed visual-command arbitration."""
from collections import OrderedDict
from dataclasses import dataclass, field
from math import hypot, isfinite
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

from spatial_zones import SpatialEngine, SpatialMap


@dataclass(frozen=True)
class LoadedImage:
    token: int
    path: Path
    image: Image.Image = field(repr=False, compare=False)


class ImageStore:
    def __init__(self, capacity=4):
        self.capacity = capacity
        self.images = OrderedDict()
        self.frames = OrderedDict()
        self.serial = 0

    def clear(self):
        self.images.clear();self.frames.clear()

    def load(self, reference, project_file):
        path = Path(reference)
        if not path.is_absolute():
            if project_file is None:raise ValueError('No es pot resoldre la imatge sense projecte.')
            path = Path(project_file).resolve().parent / path
        path = path.resolve()
        if path in self.images:
            self.images.move_to_end(path);return self.images[path]
        if path.suffix.lower() not in ('.jpg','.jpeg','.png'):raise ValueError('Format d’imatge no admès.')
        with Image.open(path) as source:
            if source.format not in ('JPEG','PNG'):raise ValueError('El fitxer no és JPG ni PNG.')
            image = ImageOps.exif_transpose(source).convert('RGBA')
            image.thumbnail((4096,4096),Image.Resampling.LANCZOS)
            rgb = Image.new('RGB',image.size,'black');rgb.paste(image,mask=image.getchannel('A'))
        self.serial += 1
        loaded = LoadedImage(self.serial,path,rgb)
        self.images[path] = loaded
        while len(self.images)>self.capacity:self.images.popitem(last=False)
        return loaded

    def fit(self, loaded, size):
        width,height = size
        if type(width) is not int or type(height) is not int or width<1 or height<1:
            raise ValueError('La mida de projecció ha de ser positiva.')
        key = loaded.token,width,height
        if key not in self.frames:
            image = ImageOps.contain(loaded.image,(width,height),Image.Resampling.LANCZOS)
            canvas = Image.new('RGB',(width,height),'black')
            canvas.paste(image,((width-image.width)//2,(height-image.height)//2))
            frame = np.array(canvas)[:,:,::-1].copy()  # OpenCV BGR, never drawn on directly.
            frame.setflags(write=False)
            self.frames[key] = frame
            while len(self.frames)>4:self.frames.popitem(last=False)
        self.frames.move_to_end(key)
        return self.frames[key]


@dataclass
class _ColorState:
    last_seen: float
    confirmed: tuple | None = None
    since: float | None = None
    count: int = 0


class ZoneProjection:
    def __init__(self, config=None, project_file=None):
        self.store = ImageStore()
        self.mode = 'live'
        self.color_card = None
        self.image = None
        self.scene = None
        self.zone_name = None
        self.last_error = None
        self.colors = {}
        self.configure(config or SpatialMap(),project_file,keep_scene=False)

    def configure(self, config, project_file, keep_scene=True):
        self.engine = SpatialEngine(config)
        self.project_file = project_file
        self.store.clear();self.colors.clear();self.last_error = None
        if not keep_scene:
            self.mode='live';self.image=None;self.scene=None;self.zone_name=None;self.color_card=None

    def request_live(self):
        self.mode='live';self.color_card=None

    def _color_events(self, observations, now):
        events=[]
        for card,point in sorted(observations.items()):
            state=self.colors.get(card)
            if state is None or now-state.last_seen>.25:
                state=_ColorState(now);self.colors[card]=state
            state.last_seen=now
            distance=hypot(point[0]-state.confirmed[0],point[1]-state.confirmed[1]) if state.confirmed else 1
            if distance<.0125:
                state.since=None;state.count=0;continue
            if state.since is None:
                if distance<.025:continue
                state.since=now;state.count=1
            else:state.count+=1
            if state.count>=3 and now-state.since+1e-12>=.15:
                state.confirmed=point;state.since=None;state.count=0;events.append(card)
        for card in list(self.colors):
            if now-self.colors[card].last_seen>.25:
                del self.colors[card]
                if self.mode=='color' and self.color_card==card:self.request_live()
        return events

    def process_camera(self, zones, colors, now):
        return self._process(zones,colors,now,False)

    def process_normalized(self, zones, colors, now):
        """Simulation-only: floor coordinates are supplied explicitly, not calibrated here."""
        return self._process(zones,colors,now,True)

    def _process(self, zones, colors, now, normalized):
        validated={}
        for card,point in colors.items():
            if type(card) is not int or not 0<=card<=15 or len(point)!=2 or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not isfinite(v) or not 0<=v<=1 for v in point):
                raise ValueError('Observació cromàtica no vàlida.')
            validated[card]=tuple(point)
        result=(self.engine.update_normalized(zones,now) if normalized else self.engine.update_camera(zones,now))
        color_events=self._color_events(validated,now)
        if result.status=='uncalibrated' and zones:
            self.last_error='Sense calibració vàlida: les zones no s’activen.'
        # In a simultaneous frame a zone wins, then the lowest authorized card ID.
        entries=[e for e in result.events if e.kind=='enter' and result.scene is not None
                 and e.zone_id==result.scene.zone_id and e.card_id==result.scene.card_id
                 and e.at==result.scene.confirmed_at]
        if entries:
            scene=result.scene
            try:loaded=self.store.load(scene.image_path,self.project_file)
            except (OSError,ValueError,Image.DecompressionBombError) as exc:
                self.last_error=f'No s’ha carregat la imatge de la zona {scene.zone_id}: {exc}'
            else:
                self.image=loaded;self.scene=scene
                self.zone_name=next(z.name for z in self.engine.map.zones if z.id==scene.zone_id)
                self.mode='zone';self.color_card=None;self.last_error=None
                return result
        if color_events:
            self.mode='color';self.color_card=min(color_events)
        return result

    def image_frame(self,size):
        if self.mode!='zone' or self.image is None:return None
        return self.store.fit(self.image,size)
