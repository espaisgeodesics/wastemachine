from collections import deque
import os
import unittest
from unittest.mock import Mock, patch
import numpy as np
from marker_tracking import MarkerTracker
from test_camera import app_module as m


class ObserverBridgeTests(unittest.TestCase):
    def app(self):
        app=m.App.__new__(m.App)
        app.marker_tracker=MarkerTracker();app.tracking_sequence=0;app.tracking_source_id=None
        app.camera_source_id='camera:0';app.tracking_enabled=True;app.tracking_errors=deque(maxlen=50)
        app.cam_index=Mock();app.cam_index.get.return_value=0
        return app

    def markers(self):
        return [np.array([[[10,10],[30,10],[30,30],[10,30]]],np.float32)]

    def test_duplicate_frame_rejection_is_logged_without_partial_state(self):
        app=self.app();corners=self.markers()
        app.observe_marker_frame(corners,np.array([[0]]),(100,100),0)
        before=app.marker_tracker.snapshot()
        app.observe_marker_frame(corners*2,np.array([[0],[0]]),(100,100),.1)
        self.assertEqual(app.marker_tracker.snapshot(),before)
        self.assertIn('Duplicate',app.tracking_errors[-1][1])
        app.observe_marker_frame(corners,np.array([[0]]),(100,100),.2)
        self.assertEqual(app.marker_tracker.snapshot()['camera:0',0].last_seen,.2)

    def test_observer_failure_is_contained_and_error_memory_is_bounded(self):
        app=self.app()
        with patch.object(app.marker_tracker,'update',side_effect=RuntimeError('injected tracking failure')):
            for i in range(80):app.observe_marker_frame([],None,(100,100),i)
        self.assertEqual(len(app.tracking_errors),50)
        self.assertIn('injected',app.tracking_errors[-1][1])

    def test_switching_source_marks_previous_source_unavailable(self):
        app=self.app();corners=self.markers()
        app.observe_marker_frame(corners,np.array([[0]]),(100,100),0)
        app.camera_source_id='camera:1'
        app.observe_marker_frame(corners,np.array([[0]]),(100,100),.1)
        self.assertEqual(app.marker_tracker.sources()['camera:0'].status,'unavailable')
        self.assertFalse(app.marker_tracker.snapshot()['camera:0',0].source_available)
        self.assertTrue(app.marker_tracker.snapshot()['camera:1',0].observed)
        with patch.object(m.time,'monotonic',return_value=2):app.observe_marker_frame()
        self.assertEqual(app.marker_tracker.snapshot()['camera:1',0].presence,'temporarily_lost')


@unittest.skipUnless(os.environ.get('DISPLAY') or os.name=='nt','Requires a graphical display')
class TrackingCameraIntegrationTests(unittest.TestCase):
    def frame(self):
        dictionary=m.cv2.aruco.getPredefinedDictionary(m.cv2.aruco.DICT_4X4_50)
        frame=np.full((300,900),255,np.uint8)
        for i in range(5):frame[80:180,20+i*175:120+i*175]=m.cv2.aruco.generateImageMarker(dictionary,i,100)
        return m.cv2.cvtColor(frame,m.cv2.COLOR_GRAY2BGR)

    def run_camera(self,enabled,observer_failure=False):
        root=m.tk.Tk()
        with patch.object(m.mido,'get_output_names',return_value=[]):app=m.App(root)
        app.arp_stop.set();app.arp_thread.join(timeout=1)
        port=Mock();app.midi=port;app.tracking_enabled=enabled;app.t0=0;app.clock_start=0
        for i in range(5):app.cards[i].update(function='Nota MIDI',note=60+i,visual=0)
        frame=self.frame();empty=np.full_like(frame,255);outputs=[];snapshots=[]
        app.display=Mock();app.camera=Mock()
        app.camera.read.side_effect=[(True,frame.copy()),(True,frame.copy()),(True,empty.copy()),(False,None)]
        failure=patch.object(app.marker_tracker,'update',side_effect=RuntimeError('observer failed')) if observer_failure else patch.object(app,'tracking_enabled',enabled)
        try:
            with failure:
                for now in (10,10.1,10.4,10.5):
                    with patch.object(m.time,'monotonic',return_value=now):app.tick()
                    outputs.append(app.last_frame.copy());snapshots.append(app.marker_tracker.snapshot())
                self.assertIsNone(app.camera)
                app.camera=Mock();app.camera.read.return_value=(True,frame.copy())
                with patch.object(m.time,'monotonic',return_value=11):app.tick()
                outputs.append(app.last_frame.copy());snapshots.append(app.marker_tracker.snapshot())
            errors=tuple(app.tracking_errors)
            for timer in root.tk.call('after','info'):root.after_cancel(timer)
            app.close()
            return [call.args[0] for call in port.send.call_args_list],outputs,snapshots,errors
        finally:
            if root.tk.call('info','commands','.'):
                for timer in root.tk.call('after','info'):root.after_cancel(timer)
                app.close()

    def test_five_real_synthetic_markers_keep_midi_and_public_frames_identical(self):
        legacy,legacy_frames,_,_=self.run_camera(False)
        messages,frames,states,errors=self.run_camera(True)
        self.assertEqual(messages,legacy)
        for actual,expected in zip(frames,legacy_frames):np.testing.assert_array_equal(actual,expected)
        self.assertFalse(errors);self.assertEqual(len(states[0]),5)
        for marker in range(5):
            key='camera:0',marker
            self.assertEqual(states[0][key].presence,'detected')
            self.assertEqual(states[2][key].presence,'temporarily_lost')
            self.assertFalse(states[3][key].source_available)
            self.assertEqual(states[4][key].first_seen,10)
            self.assertEqual(states[4][key].presence,'detected')
        self.assertEqual([msg.type for msg in messages],['note_on']*5+['note_off']*5+['note_on']*5+['note_off']*5)

    def test_observer_exception_does_not_change_legacy_outputs(self):
        legacy,expected,_,_=self.run_camera(False)
        messages,actual,_,errors=self.run_camera(True,observer_failure=True)
        self.assertEqual(messages,legacy);self.assertTrue(errors)
        for a,b in zip(actual,expected):np.testing.assert_array_equal(a,b)

if __name__=='__main__':unittest.main()
