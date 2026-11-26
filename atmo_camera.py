"""Single-owner webcam reader with a bounded latest-frame mailbox.

Only this worker opens, reads and releases the device. Tk never waits for a
camera read. A stuck native driver may need physical reconnection; do not open
another handle until the previous worker has actually finished.
"""
from dataclasses import dataclass
from threading import Event,Lock,Thread,current_thread
import time
import numpy as np


def normalise_frame(frame):
    if not isinstance(frame,np.ndarray) or frame.dtype!=np.uint8 or frame.ndim not in (2,3):
        raise ValueError('Fotograma buit o format de càmera no vàlid')
    h,w=frame.shape[:2]
    if min(h,w)<8 or max(h,w)>8192 or h*w>33_177_600:raise ValueError('Dimensions de càmera no vàlides')
    if frame.ndim==2:frame=np.repeat(frame[:,:,None],3,axis=2)
    elif frame.shape[2]==1:frame=np.repeat(frame,3,axis=2)
    elif frame.shape[2]==4:frame=frame[:,:,:3]
    elif frame.shape[2]!=3:raise ValueError('Nombre de canals de càmera no vàlid')
    if w>1280 or h>720:
        import cv2
        scale=min(1280/w,720/h)
        frame=cv2.resize(frame,(max(8,round(w*scale)),max(8,round(h*scale))),interpolation=cv2.INTER_AREA)
    result=np.array(frame,copy=True,order='C');result.setflags(write=False)
    return result


@dataclass(frozen=True)
class CameraSnapshot:
    frame:object
    sequence:int
    captured_at:float
    state:str
    error:str
    failures:int
    opens:int
    index:int
    backend:int


class CameraStream:
    def __init__(self,index,backend,capture_factory=None,clock=time.monotonic,period=1/30,retry_s=.3,read_timeout_s=2.):
        self.index=index;self.backend=backend;self.capture_factory=capture_factory;self.clock=clock
        self.period=period;self.retry_s=retry_s;self.read_timeout_s=read_timeout_s
        self.lock=Lock();self.stop=Event();self.thread=None
        self.frame=None;self.sequence=0;self.captured_at=0.;self.state='idle';self.error=''
        self.failures=0;self.opens=0;self.read_started=None
    def start(self):
        if self.thread is not None:return self
        self.state='starting';self.thread=Thread(target=self._run,name=f'atmo-camera-{self.index}',daemon=True);self.thread.start()
        return self
    @property
    def is_running(self):return self.thread is not None and self.thread.is_alive()
    def snapshot(self):
        now=self.clock()
        with self.lock:
            state,error=self.state,self.error
            if self.read_started is not None and now-self.read_started>self.read_timeout_s and not self.stop.is_set():
                state='stalled';error='La càmera no respon a la lectura. La projecció continua; tanca i reconnecta la càmera.'
            return CameraSnapshot(self.frame,self.sequence,self.captured_at,state,error,self.failures,self.opens,self.index,self.backend)
    def release(self,timeout=.1):
        self.stop.set()
        if self.thread is not None and self.thread is not current_thread():self.thread.join(timeout)
        return not self.is_running
    def _state(self,state,error=''):
        with self.lock:self.state=state;self.error=error
    def _open(self):
        if self.capture_factory is not None:return self.capture_factory(self.index,self.backend)
        import cv2
        return cv2.VideoCapture(self.index,self.backend)
    def _run(self):
        retries=0
        try:
            while not self.stop.is_set():
                capture=None;consecutive=0
                try:
                    self._state('starting' if not self.opens else 'recovering')
                    with self.lock:self.read_started=self.clock()
                    capture=self._open()
                    with self.lock:self.opens+=1;self.read_started=None
                    if not capture.isOpened():raise OSError('No es pot obrir la càmera. Comprova el dispositiu i altres aplicacions que la utilitzen.')
                    capture.set(3,640);capture.set(4,480)
                    while not self.stop.is_set():
                        started=self.clock()
                        with self.lock:self.read_started=started
                        try:
                            ok,raw=capture.read()
                            if not ok:raise OSError('La càmera no ha retornat cap fotograma')
                            frame=normalise_frame(raw)
                            stamp=self.clock()
                        except Exception as exc:
                            consecutive+=1
                            with self.lock:self.failures+=1;self.error=str(exc);self.state='recovering';self.read_started=None
                            if consecutive>=3:raise OSError(str(exc))
                            if self.stop.wait(max(.01,self.period)):break
                            continue
                        with self.lock:
                            self.read_started=None
                            if not self.stop.is_set():
                                self.frame=frame;self.sequence+=1;self.captured_at=stamp;self.state='ready';self.error=''
                        retries=0;consecutive=0
                        if self.stop.wait(max(.001,self.period-(self.clock()-started))):break
                except Exception as exc:
                    retries+=1;self._state('recovering' if retries<3 else 'error',str(exc))
                finally:
                    with self.lock:self.read_started=None
                    if capture is not None:
                        try:capture.release()
                        except Exception:pass
                if self.stop.is_set():break
                if retries>=3:break
                if self.stop.wait(min(2.,self.retry_s*2**max(0,retries-1))):break
        finally:
            with self.lock:
                self.read_started=None
                if self.stop.is_set():self.state='closed';self.error='';self.frame=None
