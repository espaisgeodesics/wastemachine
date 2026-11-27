"""Projection-only image layers. Operator maps and generated visuals stay separate."""
import math
from dataclasses import replace
from pathlib import Path
import numpy as np
from spatial_projection import ZoneProjection
from card_media import CardMediaPlayer, MEDIA_VISUAL, media_settings


def tile_boxes(count,width,height):
    if count<=0:return []
    columns=count if count<=3 else math.ceil(math.sqrt(count*width/max(1,height)))
    columns=min(count,columns)
    if count==4:columns=2
    rows=math.ceil(count/columns)
    boxes=[]
    for index in range(count):
        row,col=divmod(index,columns)
        # The last row fills its width, with no empty image placeholders.
        cells=min(columns,count-row*columns)
        boxes.append((col*width//cells,row*height//rows,(col+1)*width//cells,(row+1)*height//rows))
    return boxes


class ProjectionMosaic:
    def __init__(self):
        self.config=None;self.project=None;self.zones={};self.zone_active=[]
        self.cards={};self.revision=None;self.error=''

    def reset(self):
        for player in self.cards.values():player.close()
        self.cards={};self.zones={};self.config=None;self.zone_active=[];self.revision=None

    def update(self,config,project,observations,active,cards,paused,muted,now,normalized=False):
        if config!=self.config or project!=self.project:
            self.config,self.project=config,project
            self.zones={zone.id:ZoneProjection(replace(config,zones=(replace(zone,allow_overlap=False),)),project)
                        for zone in config.zones if zone.enabled and zone.image_path}
        self.zone_active=[];self.error=''
        for id,player in self.zones.items():
            result=(player.process_normalized if normalized else player.process_camera)(observations,{},now)
            occupied=any(player.engine.confirmed_zone(i)==id for i in range(16))
            if player.mode=='zone' and (occupied or player.display_mode=='after_exit' and player.deadline is not None):self.zone_active.append(id)
            if player.last_error:self.error=player.last_error
        desired={i for i in active if not muted and cards[i].get('visual')==MEDIA_VISUAL and cards[i].get('function')!='Cap acció'}
        for i in desired:
            if i not in self.cards:self.cards[i]=CardMediaPlayer()
        for i,player in list(self.cards.items()):
            settings=media_settings(cards[i],required=True) if i in desired else None
            key=None
            if settings is not None:
                path=Path(settings['media_path'])
                if not path.is_absolute():
                    if project is None:raise ValueError('Desa el projecte per resoldre les imatges de targetes')
                    path=Path(project).resolve().parent/path
                key=(str(path.resolve()),settings['media_loop'],i)
            player.request(key,settings);player.decoder.set_paused(paused)
            if player.decoder.snapshot()[1]:self.error=player.decoder.snapshot()[1]
            if key is None and not player.needs_update():player.close();del self.cards[i]
        signature=(tuple((id,self.zones[id].image.token) for id in self.zone_active),
                   tuple((i,p.key,p.decoder.snapshot()[2],p.needs_update()) for i,p in sorted(self.cards.items())))
        changed=signature!=self.revision or any(p.needs_update() for p in self.cards.values())
        self.revision=signature
        return changed

    def frame(self,size):
        sources=[('zone',id) for id in sorted(self.zone_active)]
        sources += [('card',i) for i,p in sorted(self.cards.items()) if p.decoder.snapshot()[0] is not None or p.tail is not None]
        if not sources:return None
        width,height=size;result=np.zeros((height,width,3),np.uint8)
        for (kind,id),(left,top,right,bottom) in zip(sources,tile_boxes(len(sources),width,height)):
            w,h=right-left,bottom-top
            if w<1 or h<1:continue
            if kind=='zone':frame=self.zones[id].image_frame((w,h))
            else:frame=self.cards[id].apply(np.zeros((h,w,3),np.uint8))
            if frame is not None:result[top:bottom,left:right]=frame
        return result
