"""Single audio worker: optional imports, decoding and SDL stay off Tk/MIDI threads."""
from collections import deque
from dataclasses import dataclass
from threading import Condition, Event, Thread
import time

from local_audio import AudioEngine, AudioCommand, PygameAudioBackend


@dataclass(frozen=True)
class AudioStatus:
    state: str
    detail: str
    voices: tuple
    cache_bytes: int
    queued: int
    log: tuple


class AudioController:
    def __init__(self, factory=PygameAudioBackend):
        self.factory=factory
        self.condition=Condition()
        self.cancel=Event()
        self.queue=deque()
        self.log=deque(maxlen=100)
        self.engine=None
        self.state='disabled';self.detail='Àudio local desactivat'
        self.voices=();self.cache_bytes=0
        self.master=1.
        self.closing=False
        self.thread=None

    def _wake(self):
        if self.thread is None:
            self.thread=Thread(target=self._run,name='atmo-local-audio',daemon=True);self.thread.start()
        self.condition.notify_all()

    def snapshot(self):
        with self.condition:
            return AudioStatus(self.state,self.detail,self.voices,self.cache_bytes,len(self.queue),tuple(self.log))

    def enable(self):
        with self.condition:
            if self.closing:return False
            if self.state in ('ready','starting'):return True
            self.state='starting';self.detail='Activant el dispositiu local...'
            self.queue.append(('enable',None));self._wake();return True

    def submit(self,command):
        if not isinstance(command,AudioCommand):raise ValueError('Ordre d’àudio no vàlida')
        with self.condition:
            if self.closing or self.state!='ready':return False
            if len(self.queue)>=128:
                self.detail='Cua d’àudio plena; ordre rebutjada';self.log.append((time.monotonic(),'cua',self.detail))
                raise ValueError(self.detail)
            self.queue.append(('command',command));self._wake();return True

    def set_master(self,gain):
        if isinstance(gain,bool) or not isinstance(gain,(int,float)) or not 0<=gain<=1:raise ValueError('Volum màster no vàlid')
        with self.condition:
            self.master=float(gain);self.condition.notify_all()

    def stop_all(self):
        with self.condition:
            if self.thread is None or self.closing:return
            self.cancel.set();self.queue.clear();self.queue.append(('stop',None));self._wake()

    def disable(self):
        with self.condition:
            if self.thread is None or self.closing:return
            self.cancel.set();self.queue.clear();self.queue.append(('disable',None))
            self.state='stopping';self.detail='Aturant àudio local...';self._wake()

    def close(self,timeout=2):
        with self.condition:
            self.closing=True
            if self.thread is None:self.state='disabled';return True
            self.state='stopping';self.detail='Aturant àudio local...'
            self.cancel.set();self.queue.clear();self.queue.append(('close',None));self._wake()
            thread=self.thread
        thread.join(timeout)
        return not thread.is_alive()

    def _publish(self):
        voices=self.engine.snapshot() if self.engine is not None else ()
        size=self.engine.backend.cache_bytes if self.engine is not None else 0
        with self.condition:self.voices=voices;self.cache_bytes=size

    def _close_engine(self):
        if self.engine is not None:
            try:self.engine.close()
            except Exception as exc:
                with self.condition:self.log.append((time.monotonic(),'tancament',str(exc)))
            finally:self.engine=None

    def _run(self):
        try:
            while True:
                with self.condition:
                    if not self.queue:self.condition.wait(.02)
                    item=self.queue.popleft() if self.queue else None
                    master=self.master
                now=time.monotonic()
                if item is not None:
                    kind,command=item
                    if kind=='close':break
                    if kind in ('disable','enable'):
                        self._close_engine()
                        if kind=='enable':
                            try:
                                self.engine=AudioEngine(self.factory())
                                with self.condition:
                                    if not self.closing:self.state='ready';self.detail=getattr(self.engine.backend,'description','Àudio local actiu')
                            except Exception as exc:
                                with self.condition:self.state='error';self.detail=str(exc);self.log.append((now,'activació',str(exc)))
                        else:
                            with self.condition:self.state='disabled';self.detail='Àudio local desactivat'
                        self.cancel.clear()
                    elif kind=='stop':
                        try:
                            if self.engine is not None:self.engine.stop_all()
                        except Exception as exc:
                            self._close_engine()
                            with self.condition:self.state='error';self.detail=str(exc)
                        self.cancel.clear()
                        with self.condition:self.log.append((now,'aturada','Totes les veus locals aturades'))
                    elif self.engine is not None:
                        try:
                            self.engine.master=master
                            result=self.engine.dispatch(command,now,self.cancel.is_set,time.monotonic)
                            with self.condition:self.log.append((now,command.kind,('cancel·lada per aturada' if result is False else 'acceptada: '+command.group)))
                        except Exception as exc:
                            with self.condition:self.log.append((now,command.kind,str(exc)));self.detail=str(exc)
                if self.engine is not None:
                    try:
                        self.engine.master=master;self.engine.tick(time.monotonic())
                    except Exception as exc:
                        self._close_engine()
                        with self.condition:
                            self.state='error';self.detail=str(exc);self.log.append((now,'dispositiu',str(exc)))
                            self.queue=deque(item for item in self.queue if item[0] in ('close','disable'))
                self._publish()
        except Exception as exc:
            with self.condition:self.state='error';self.detail=str(exc);self.log.append((time.monotonic(),'backend',str(exc)))
        finally:
            try:self._close_engine()
            finally:
                with self.condition:
                    self.voices=();self.cache_bytes=0
                    if self.closing:self.state='disabled';self.detail='Àudio local tancat'
                    self.thread=None
