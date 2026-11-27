import threading,time,unittest
from unittest.mock import Mock
import numpy as np
from atmo_camera import CameraStream,normalise_frame


def wait_for(condition,seconds=2):
    until=time.monotonic()+seconds
    while time.monotonic()<until:
        if condition():return True
        time.sleep(.005)
    return condition()


class FrameTests(unittest.TestCase):
    def test_rejects_empty_bad_dimensions_and_formats(self):
        for frame in (None,np.zeros((0,8,3),np.uint8),np.zeros((10,10,2),np.uint8),np.zeros((10,10,3),float),np.zeros((3,3,3),np.uint8),'screen'):
            with self.subTest(shape=getattr(frame,'shape',None)):
                with self.assertRaises(ValueError):normalise_frame(frame)
    def test_frames_are_copied_read_only_and_bounded(self):
        source=np.full((1080,1920,3),42,np.uint8)
        frame=normalise_frame(source)
        self.assertEqual(frame.shape,(720,1280,3));self.assertFalse(frame.flags.writeable)
        source[:]=0;self.assertEqual(frame[0,0,0],42)
    def test_grayscale_and_bgra_are_supported(self):
        for source in (np.full((20,30),7,np.uint8),np.full((20,30,1),7,np.uint8),np.full((20,30,4),7,np.uint8)):
            frame=normalise_frame(source);self.assertEqual(frame.shape,(20,30,3));self.assertTrue((frame==7).all())


class ReaderTests(unittest.TestCase):
    def capture(self):
        c=Mock();c.isOpened.return_value=True;c.read.return_value=(True,np.zeros((48,64,3),np.uint8));return c
    def stream(self,factory,**options):
        s=CameraStream(2,700,capture_factory=factory,period=.002,retry_s=.01,**options).start()
        self.addCleanup(s.release);return s
    def test_single_worker_owns_open_read_release_and_does_not_touch_tk(self):
        c=self.capture();owners=[]
        c.read.side_effect=lambda:(owners.append(threading.current_thread().name) or True,np.full((48,64,3),42,np.uint8))
        opened=[]
        def factory(*args):opened.append((args,threading.current_thread().name));return c
        s=self.stream(factory);self.assertTrue(wait_for(lambda:s.snapshot().sequence>=4))
        self.assertEqual(opened,[((2,700),'atmo-camera-2')]);self.assertTrue(all(name=='atmo-camera-2' for name in owners))
        self.assertTrue(s.release());c.release.assert_called_once()
        self.assertEqual(s.snapshot().state,'closed')
    def test_hung_read_never_blocks_snapshot_or_starts_another_device(self):
        entered=threading.Event();unblock=threading.Event();c=self.capture()
        def blocked():entered.set();unblock.wait(2);return True,np.zeros((48,64,3),np.uint8)
        c.read.side_effect=blocked;factory=Mock(return_value=c)
        s=self.stream(factory,read_timeout_s=.02)
        self.addCleanup(unblock.set);self.assertTrue(entered.wait(1));time.sleep(.025)
        before=time.monotonic();snap=s.snapshot();self.assertLess(time.monotonic()-before,.05)
        self.assertEqual(snap.state,'stalled')
        self.assertFalse(s.release(timeout=.01));factory.assert_called_once();c.release.assert_not_called()
        unblock.set();self.assertTrue(wait_for(lambda:not s.is_running));c.release.assert_called_once()
    def test_bad_frames_recover_using_one_open_handle(self):
        c=self.capture();c.read.side_effect=[(True,None),(True,np.zeros((0,10,3),np.uint8)),(True,np.ones((48,64,3),np.uint8))]+[(True,np.ones((48,64,3),np.uint8))]*30
        factory=Mock(return_value=c);s=self.stream(factory)
        self.assertTrue(wait_for(lambda:s.snapshot().sequence>=2))
        self.assertEqual(s.snapshot().failures,2);factory.assert_called_once();self.assertEqual(s.snapshot().state,'ready')
    def test_reader_reopens_after_repeated_failures_and_releases_old_handle(self):
        broken=self.capture();broken.read.return_value=(False,None);healthy=self.capture()
        factory=Mock(side_effect=[broken,healthy]);s=self.stream(factory)
        self.assertTrue(wait_for(lambda:s.snapshot().sequence>=2))
        self.assertEqual(s.snapshot().opens,2);broken.release.assert_called_once();self.assertEqual(s.snapshot().failures,3)
    def test_failed_open_attempts_are_bounded(self):
        c=self.capture();c.isOpened.return_value=False;factory=Mock(return_value=c);s=self.stream(factory)
        self.assertTrue(wait_for(lambda:not s.is_running))
        self.assertEqual(factory.call_count,3);self.assertEqual(c.release.call_count,3);self.assertEqual(s.snapshot().state,'error')
    def test_static_scene_is_not_mistaken_for_a_frozen_driver(self):
        c=self.capture();factory=Mock(return_value=c);s=self.stream(factory)
        self.assertTrue(wait_for(lambda:s.snapshot().sequence>=20))
        self.assertEqual(s.snapshot().state,'ready');factory.assert_called_once()
    def test_mailbox_has_only_latest_frame_and_no_growth_with_frame_count(self):
        c=self.capture();counter=[0]
        def read():
            counter[0]+=1
            return True,np.full((48,64,3),counter[0]%255,np.uint8)
        c.read.side_effect=read;s=CameraStream(2,700,capture_factory=lambda *args:c,period=0,retry_s=.01).start();self.addCleanup(s.release)
        self.assertTrue(wait_for(lambda:s.snapshot().sequence>=200))
        packet=s.snapshot();self.assertIs(packet.frame,s.snapshot().frame)
        self.assertEqual(packet.frame.nbytes,48*64*3)
        self.assertFalse(any(isinstance(value,list) for value in vars(s).values()))

if __name__=='__main__':unittest.main()
