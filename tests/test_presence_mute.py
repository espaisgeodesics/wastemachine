import unittest
from unittest.mock import Mock, patch
import test_audio
from test_camera import app_module as m

class PresenceMuteTests(unittest.TestCase):
    def app(self):
        a=test_audio.AudioTests().app()
        a.cards[0].update(function=m.MUTE_FUNCTION,channel=1,cc=119,mute_audible=0,mute_silent=127)
        a.mute_sent={};a.mute_retry_after={};a.last_seen={};a._closing=False
        return a

    def values(self,a):return [(c.args[0].type,c.args[0].channel,c.args[0].control,c.args[0].value) for c in a.midi.send.call_args_list]

    def test_absent_visible_absent_repeats_without_notes_or_toggles(self):
        a=self.app();a.sync_mute_controls();a.sync_mute_controls()
        a.activate(0,.5,.5,0);a.activate(0,.6,.5,0);a.last_seen[0]=10
        a.expire_missing_cards(set(),10.24)
        self.assertEqual(len(self.values(a)),2)
        a.expire_missing_cards(set(),10.26);a.sync_mute_controls()
        a.activate(0,.5,.5,0);a.deactivate(0)
        self.assertEqual(self.values(a),[('control_change',0,119,v) for v in (127,0,127,0,127)])
        self.assertFalse(a.notes)

    def test_failure_is_retried_after_backoff_for_absent_state(self):
        a=self.app()
        with patch.object(m.time,'monotonic',return_value=10):a.activate(0,.5,.5,0)
        a.midi.send.side_effect=[RuntimeError('Port failure'),None]
        with patch.object(m.time,'monotonic',return_value=11):a.deactivate(0)
        self.assertEqual(a.mute_sent[0][-1],0)
        with patch.object(m.time,'monotonic',return_value=11.2):a.sync_mute_controls()
        self.assertEqual(a.midi.send.call_count,2)
        with patch.object(m.time,'monotonic',return_value=11.6):a.sync_mute_controls()
        self.assertEqual(a.midi.send.call_count,3);self.assertEqual(a.mute_sent[0][-1],127)

    def test_emergency_and_close_silence_even_visible_cards(self):
        for closing in (True,False):
            a=self.app();a.activate(0,.5,.5,0)
            a._closing=closing;a.muted=not closing
            a.sync_mute_controls()
            self.assertEqual(self.values(a)[-1],('control_change',0,119,127))
            a.activate(0,.5,.5,0);a.sync_mute_controls()
            self.assertEqual(self.values(a)[-1][-1],127)

    def test_all_notes_off_silences_presence_without_transport_messages(self):
        a=self.app();a.activate(0,.5,.5,0);a.all_notes_off()
        self.assertEqual(self.values(a),[('control_change',0,119,0),('control_change',0,119,127)])

    def test_custom_values_and_channel_are_explicit(self):
        a=self.app();a.cards[0].update(channel=3,cc=118,mute_audible=127,mute_silent=0)
        a.sync_mute_controls();a.activate(0,.5,.5,0);a.deactivate(0)
        self.assertEqual(self.values(a),[('control_change',2,118,v) for v in (0,127,0)])

if __name__=='__main__':unittest.main()
