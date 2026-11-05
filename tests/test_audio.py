import threading
import unittest
from unittest.mock import Mock, patch
from test_camera import app_module as m

class AudioTests(unittest.TestCase):
    def app(self):
        a=m.App.__new__(m.App)
        a.cards=[dict(m.DEFAULTS[i],function='Àudio',audio_duration=10) for i in range(16)]
        a.midi=Mock();a.status=Mock();a.muted=False;a.audio_states={};a.audio_error=None;a.arp_lock=threading.RLock()
        a.target_trails={};a.audio_cc_values={};a.active={};a.last_cc={};a.notes={};a.harmony_notes={};a.harmony_zones={};a.harmony_pending={};a.queued_harmony={};a.arp_states={}
        a.preview_card=None;a.preview_caption=Mock();a.preview_dirty=False
        a.follow_live_preview=Mock();a.select_visual=Mock();a.visual_dirty=False
        return a

    def hits(self,a):return [c.args[0] for c in a.midi.send.call_args_list if c.args[0].type=='note_on']

    def test_repeated_detection_and_reappearance_do_not_restart_clip(self):
        a=self.app()
        with patch.object(m.time,'monotonic',return_value=100):
            for i in range(10):a.activate(0,.5,.5,0)
            a.deactivate(0)
            self.assertEqual(a.midi.send.call_count,1)
            a.activate(0,.5,.5,0)
        self.assertEqual(len(self.hits(a)),1)
        self.assertEqual(a.audio_states[0]['ends_at'],110)

    def test_pulse_release_does_not_unlock_clip_and_end_requires_new_detection(self):
        a=self.app()
        with patch.object(m.time,'monotonic',return_value=100):a.activate(0,.5,.5,0)
        a.audio_tick(100.1)
        self.assertEqual(a.midi.send.call_args.args[0].type,'note_off')
        self.assertIn(0,a.audio_states)
        a.audio_tick(110)
        with patch.object(m.time,'monotonic',return_value=111):
            a.activate(0,.5,.5,0)
            self.assertEqual(len(self.hits(a)),1)
            a.deactivate(0);a.activate(0,.5,.5,0)
        self.assertEqual(len(self.hits(a)),2)

    def test_duplicate_clip_mapping_is_blocked_across_cards(self):
        a=self.app();a.cards[1]['note']=a.cards[0]['note']
        with patch.object(m.time,'monotonic',return_value=100):
            a.trigger_audio(0);a.trigger_audio(1)
        self.assertEqual(len(self.hits(a)),1)

    def test_invalid_duration_missing_port_and_mute_never_send(self):
        for duration in (0,-1,float('nan'),float('inf')):
            a=self.app();a.cards[0]['audio_duration']=duration;a.trigger_audio(0)
            a.midi.send.assert_not_called()
        a=self.app();a.muted=True;a.trigger_audio(0);a.midi.send.assert_not_called()
        a=self.app();a.midi=None;a.trigger_audio(0);self.assertFalse(a.audio_states)

    def test_independent_clips_can_play_and_short_clips_release_notes(self):
        a=self.app();a.cards[0]['audio_duration']=.01
        with patch.object(m.time,'monotonic',return_value=100):
            a.trigger_audio(0);a.trigger_audio(1)
        self.assertEqual(len(self.hits(a)),2)
        a.audio_tick(100.02)
        self.assertNotIn(0,a.audio_states)
        self.assertIn(1,a.audio_states)
        self.assertEqual(a.midi.send.call_args.args[0].type,'note_off')

    def test_motion_controls_ranges_and_no_reset_on_removal(self):
        a=self.app()
        a.cards[0]['audio_controls']={
            'volume':dict(m.AUDIO_CONTROLS['volume'],enabled=True,min=40,max=100),
            'pan':dict(m.AUDIO_CONTROLS['pan'],enabled=True),
            'effect':dict(m.AUDIO_CONTROLS['effect'],enabled=True,cc=91),
        }
        with patch.object(m.time,'monotonic',return_value=100):a.activate(0,.25,.75,.5)
        messages=[c.args[0] for c in a.midi.send.call_args_list]
        self.assertEqual({x.control:x.value for x in messages if x.type=='control_change'},{7:55,10:32,91:64})
        self.assertEqual(messages[-1].type,'note_on')
        count=a.midi.send.call_count
        a.activate(0,.25,.75,.5)
        self.assertEqual(a.midi.send.call_count,count)
        a.deactivate(0)
        self.assertEqual(a.midi.send.call_count,count)
        with patch.object(m.time,'monotonic',return_value=101):a.activate(0,.75,.25,.25)
        messages=[c.args[0] for c in a.midi.send.call_args_list]
        self.assertEqual(len(self.hits(a)),1)
        self.assertEqual({x.control:x.value for x in messages if x.type=='control_change'},{7:85,10:95,91:32})

    def test_motion_default_off_and_radial_bounds(self):
        a=self.app();a.send_audio_controls(0,.5,.5,0)
        a.midi.send.assert_not_called()
        a.cards[0]['audio_controls']={'effect':dict(m.AUDIO_CONTROLS['effect'],enabled=True,axis='Distància al centre',min=20,max=100)}
        a.send_audio_controls(0,.5,.5,0)
        self.assertEqual(a.midi.send.call_args.args[0].value,20)
        a.send_audio_controls(0,1,1,0)
        self.assertEqual(a.midi.send.call_args.args[0].value,100)
        a.muted=True;count=a.midi.send.call_count;a.send_audio_controls(0,0,0,0)
        self.assertEqual(a.midi.send.call_count,count)

if __name__=='__main__':unittest.main()
