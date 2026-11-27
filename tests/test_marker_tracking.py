from dataclasses import FrozenInstanceError
import unittest
import numpy as np
from marker_tracking import MarkerObservation as Observation, ObservationFrame as Frame, MarkerTracker
from aruco_observations import observation_frame


def obs(marker=0, x=.5, y=.5, angle=0):
    return Observation(marker,(x,y),angle)


class TrackingTests(unittest.TestCase):
    def test_five_markers_reordered_keep_independent_identities(self):
        tracker=MarkerTracker()
        first=tracker.update(Frame('camera:0',0,0,tuple(obs(i,i/10,.4) for i in range(5))))
        second=tracker.update(Frame('camera:0',1,.1,tuple(obs(i,i/10,.6) for i in reversed(range(5)))))
        self.assertEqual(len(second),5)
        for i in range(5):
            state=second['camera:0',i]
            self.assertEqual(state.last_observation.position,(i/10,.6))
            self.assertEqual(state.first_seen,0);self.assertTrue(state.observed)
            self.assertEqual(first['camera:0',i].last_observation.position,(i/10,.4))

    def test_short_loss_absence_and_return_preserve_first_seen(self):
        tracker=MarkerTracker(absence_after_s=1)
        tracker.update(Frame('a',0,0,(obs(),)))
        state=tracker.update(Frame('a',1,.1))['a',0]
        self.assertEqual(state.presence,'temporarily_lost');self.assertFalse(state.observed)
        self.assertEqual(state.last_observation.position,(.5,.5));self.assertEqual(state.age_s,.1)
        self.assertEqual(tracker.update(Frame('a',2,1))['a',0].presence,'absent')
        state=tracker.update(Frame('a',3,1.1,(obs(x=.7),)))['a',0]
        self.assertEqual(state.presence,'detected');self.assertEqual(state.first_seen,0)
        self.assertEqual(state.age_s,0)

    def test_outage_is_not_confirmed_absence_or_retirement(self):
        tracker=MarkerTracker();tracker.update(Frame('a',0,0,(obs(),)))
        for sequence,now in ((1,2),(2,100)):
            state=tracker.update(Frame('a',sequence,now,status='unavailable'))['a',0]
            self.assertEqual(state.presence,'temporarily_lost');self.assertFalse(state.source_available)
            self.assertFalse(state.observed);self.assertEqual(state.last_seen,0)
        self.assertEqual(tracker.sources()['a'].status,'unavailable')
        state=tracker.update(Frame('a',3,101,(obs(),)))['a',0]
        self.assertEqual(state.first_seen,0);self.assertTrue(state.source_available)

    def test_explicit_retirement_does_not_happen_from_loss(self):
        tracker=MarkerTracker();tracker.update(Frame('a',0,0,(obs(),)))
        tracker.retire('a',0)
        self.assertEqual(tracker.update(Frame('a',1,.1,(obs(),)))['a',0].presence,'retired')
        self.assertFalse(tracker.snapshot()['a',0].observed)
        with self.assertRaises(ValueError):tracker.retire('a',True)

    def test_source_ids_separate_equal_marker_ids_and_clocks(self):
        tracker=MarkerTracker()
        tracker.update(Frame('a',0,100,(obs(x=.2),)))
        tracker.update(Frame('b',0,1,(obs(x=.8),)))
        tracker.update(Frame('a',1,101))
        self.assertEqual(tracker.snapshot()['a',0].presence,'absent')
        self.assertEqual(tracker.snapshot()['b',0].presence,'detected')
        self.assertEqual(tracker.snapshot()['b',0].last_observation.position,(.8,.5))

    def test_invalid_frame_or_order_never_partially_modifies_state(self):
        tracker=MarkerTracker();tracker.update(Frame('a',2,2,(obs(),)))
        before=tracker.snapshot();sources=tracker.sources()
        for frame in (Frame('a',3,2,(obs(x=.7),)),Frame('a',2,3,(obs(x=.7),)),object()):
            with self.assertRaises(ValueError):tracker.update(frame)
            self.assertEqual(tracker.snapshot(),before);self.assertEqual(tracker.sources(),sources)
        with self.assertRaises(ValueError):Frame('a',3,3,(obs(),obs()))
        self.assertEqual(tracker.snapshot(),before)

    def test_invalid_observations_and_metadata_are_rejected(self):
        for marker in (-1,16,True):
            with self.assertRaises(ValueError):obs(marker)
        for x in (-.1,1.1,float('nan'),float('inf'),True):
            with self.assertRaises(ValueError):obs(x=x)
        for angle in (-.1,1,float('nan')):
            with self.assertRaises(ValueError):obs(angle=angle)
        for kwargs in ({'status':'bad'},{'coordinate_space':'floor'},{'status':'unavailable','observations':(obs(),)}):
            with self.assertRaises(ValueError):Frame('a',0,0,**kwargs)
        with self.assertRaises(ValueError):Frame('a',0,float('nan'))
        with self.assertRaises(ValueError):Frame('',0,0)
        with self.assertRaises(ValueError):Frame('a',True,0)

    def test_snapshots_and_history_are_immutable_and_bounded(self):
        tracker=MarkerTracker(history_limit=3,history_duration_s=.25)
        for i in range(10):tracker.update(Frame('a',i,i*.1,(obs(),)))
        snapshot=tracker.snapshot();state=snapshot['a',0]
        self.assertEqual(len(state.history),3)
        with self.assertRaises(TypeError):snapshot['a',1]=state
        with self.assertRaises(FrozenInstanceError):state.presence='absent'
        tracker.update(Frame('a',10,2,status='unavailable'))
        self.assertFalse(tracker.snapshot()['a',0].history)
        self.assertEqual(len(snapshot['a',0].history),3)
        self.assertEqual(tracker.snapshot()['a',0].last_observation.position,(.5,.5))

    def test_source_capacity_cannot_grow_unbounded(self):
        tracker=MarkerTracker(max_sources=1);tracker.update(Frame('a',0,0,(obs(),)))
        with self.assertRaises(ValueError):tracker.update(Frame('b',0,0,(obs(),)))
        self.assertEqual(len(tracker.sources()),1);self.assertEqual(len(tracker.snapshot()),1)
        for kwargs in ({'max_sources':0},{'history_limit':0},{'absence_after_s':float('nan')},{'history_duration_s':0}):
            with self.assertRaises(ValueError):MarkerTracker(**kwargs)


class ArucoObservationTests(unittest.TestCase):
    def corners(self,x=10,y=20):
        return np.array([[[x,y],[x+20,y],[x+20,y+20],[x,y+20]]],np.float32)

    def test_conversion_uses_original_dimensions_and_legacy_angle(self):
        frame=observation_frame([self.corners()],np.array([[4]]),(100,200),'a',0,0)
        observation=frame.observations[0]
        self.assertEqual(observation.marker_id,4);np.testing.assert_allclose(observation.position,(.2,.15),atol=1e-7)
        self.assertEqual(observation.orientation,0);self.assertEqual(observation.corners[0],(.1,.1))
        self.assertEqual(frame.coordinate_space,'camera_normalized')

    def test_duplicate_detector_id_rejected_as_one_frame(self):
        with self.assertRaisesRegex(ValueError,'Duplicate'):
            observation_frame([self.corners(),self.corners(50)],np.array([[4],[4]]),(100,200),'a',0,0)

    def test_empty_frame_differs_from_unavailable_and_unsupported_ids_are_filtered(self):
        empty=observation_frame([],None,(100,200),'a',0,0)
        self.assertEqual(empty.status,'ok');self.assertFalse(empty.observations)
        frame=observation_frame([self.corners()],np.array([[49]]),(100,200),'a',1,.1)
        self.assertFalse(frame.observations)
        with self.assertRaises(ValueError):observation_frame([self.corners()],None,(100,200),'a',1,.1)
        with self.assertRaises(ValueError):observation_frame([self.corners()],np.array([[1],[2]]),(100,200),'a',1,.1)
        with self.assertRaises(ValueError):observation_frame([],None,(0,200),'a',1,.1)

if __name__=='__main__':unittest.main()
