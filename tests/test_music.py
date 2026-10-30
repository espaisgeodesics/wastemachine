import threading
import unittest
from unittest.mock import Mock
from test_camera import app_module as m

class MusicTests(unittest.TestCase):
    def app(self, function='Arpegiador espacial'):
        a=m.App.__new__(m.App)
        a.cards=[dict(m.DEFAULTS[0],function=function,arp_direction='Ascendent',rhythm_pattern=[i in (0,3) for i in range(16)],arp_division='1/4 temps',note=36,channel=10)]
        a.arp_states={0:dict(pitches=[60,64,67],index=0,last_step=None,playing=None,off_at=0)}
        a.midi=Mock();a.bpm=120;a.metronome_start=0;a.muted=False
        return a

    def test_directions_emit_expected_midi(self):
        for direction,expected in [('Ascendent',[60,64,67,60,64,67]),('Descendent',[67,64,60,67,64,60]),('Pujada i baixada',[60,64,67,64,60,64])]:
            with self.subTest(direction=direction):
                a=self.app();a.cards[0]['arp_direction']=direction
                for step in range(6):a.sequencer_tick(step*.125)
                messages=[c.args[0] for c in a.midi.send.call_args_list]
                self.assertEqual([x.note for x in messages if x.type=='note_on'],expected)
                self.assertTrue(all(x.channel==9 for x in messages))

    def test_random_notes_stay_in_chord(self):
        a=self.app();a.cards[0]['arp_direction']='Aleatori'
        for step in range(20):a.sequencer_tick(step*.125)
        notes=[c.args[0].note for c in a.midi.send.call_args_list if c.args[0].type=='note_on']
        self.assertEqual(len(notes),20)
        self.assertTrue(set(notes)<={60,64,67})

    def test_rhythm_rests_gate_and_loop(self):
        a=self.app('Patró rítmic')
        for step in range(17):a.sequencer_tick(step*.125)
        messages=[c.args[0] for c in a.midi.send.call_args_list]
        self.assertEqual([x.note for x in messages if x.type=='note_on'],[36,36,36])
        self.assertEqual(sum(x.type=='note_off' for x in messages),2)
        a.sequencer_tick(2.1)
        self.assertEqual(a.midi.send.call_args.args[0].type,'note_off')

    def test_no_repeated_step_or_catchup_burst(self):
        a=self.app()
        for now in (0,.01,.02,10):a.sequencer_tick(now)
        self.assertEqual(sum(c.args[0].type=='note_on' for c in a.midi.send.call_args_list),2)

    def test_panic_sends_all_channels_and_blocks_activation(self):
        a=self.app();a.arp_lock=threading.RLock()
        a.sim_card=None;a.sim_xy=None;a.active={};a.notes={};a.queued_harmony={}
        a.harmony_notes={};a.harmony_pending={};a.last_cc={};a.card2_cc_values={}
        a.panic_button=Mock();a.status=Mock()
        a.toggle_panic()
        self.assertTrue(a.muted);self.assertFalse(a.arp_states)
        messages=[c.args[0] for c in a.midi.send.call_args_list]
        self.assertEqual({(x.channel,x.control) for x in messages if x.type=='control_change'}, {(ch,cc) for ch in range(16) for cc in (64,120,123)})
        count=a.midi.send.call_count
        a.sequencer_tick(1)
        a.activate(0,.5,.5,0)
        self.assertEqual(a.midi.send.call_count,count)
        self.assertFalse(a.active)
        a.toggle_panic();self.assertFalse(a.muted)

if __name__=='__main__':unittest.main()
