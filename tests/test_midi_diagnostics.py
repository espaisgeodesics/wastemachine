import unittest
from unittest.mock import Mock
from test_camera import app_module as m
import test_audio

class MidiDiagnosticTests(unittest.TestCase):
    app=test_audio.AudioTests.app

    def traced_app(self):
        a=self.app();port=Mock();a.last_seen={}
        a.midi=m.TracedMidiOutput(port,lambda message,error:a.record_midi_send('wasteland MIDI 1',message,error))
        a.cards[2]['function']='Nota MIDI';a.cards[2]['channel']=1;a.cards[2]['note']=60
        return a,port

    def test_repeated_presence_and_absence_emit_matching_pairs_with_timeout(self):
        a,port=self.traced_app()
        a.activate(2,.5,.5,0);a.last_seen[2]=10
        a.activate(2,.6,.5,0)
        a.expire_missing_cards(set(),10.24)
        self.assertIn(2,a.active)
        self.assertEqual(port.send.call_count,1)
        a.expire_missing_cards(set(),10.26)
        self.assertNotIn(2,a.active);self.assertNotIn(2,a.notes)
        a.activate(2,.5,.5,0);a.last_seen[2]=11
        a.expire_missing_cards(set(),11.26)
        messages=[call.args[0] for call in port.send.call_args_list]
        self.assertEqual([msg.type for msg in messages],['note_on','note_off','note_on','note_off'])
        self.assertEqual([(msg.channel,msg.note) for msg in messages],[(0,60)]*4)
        log=a.midi_log_snapshot()
        self.assertEqual(log.count('VISIBLE T03'),2)
        self.assertEqual(log.count('RETIRADA T03'),2)
        self.assertIn('note_off canal=1 nota=60 velocitat=0',log)
        self.assertIn('ACCEPTAT PEL PORT LOCAL [wasteland MIDI 1]',log)
        self.assertRegex(log,r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}')

    def test_failed_note_off_remains_visible_in_log(self):
        a,port=self.traced_app()
        port.send.side_effect=[None,RuntimeError('Port tancat')]
        a.activate(2,.5,.5,0);a.deactivate(2)
        log=a.midi_log_snapshot()
        self.assertIn('ERROR LOCAL [wasteland MIDI 1] note_off canal=1 nota=60 velocitat=0 | Port tancat',log)
        self.assertNotIn('ACCEPTAT PEL PORT LOCAL [wasteland MIDI 1] note_off',log)

    def test_trace_callback_cannot_break_or_duplicate_sending(self):
        port=Mock();record=Mock(side_effect=RuntimeError('Logger'))
        output=m.TracedMidiOutput(port,record)
        message=m.mido.Message('note_on',note=60)
        output.send(message);port.send.assert_called_once_with(message)
        output.close();port.close.assert_called_once()
        port.send.side_effect=ValueError('MIDI failure')
        with self.assertRaisesRegex(ValueError,'MIDI failure'):output.send(message)

    def test_probe_sends_only_requested_cc_and_respects_mute(self):
        a,port=self.traced_app();a.probe_channel=Mock();a.probe_cc=Mock()
        a.probe_channel.get.return_value=1;a.probe_cc.get.return_value=119
        for value in (0,0,127,127):a.send_probe_cc(value)
        messages=[call.args[0] for call in port.send.call_args_list]
        self.assertEqual([(msg.type,msg.channel,msg.control,msg.value) for msg in messages],[('control_change',0,119,v) for v in (0,0,127,127)])
        a.muted=True;a.send_probe_cc(0);self.assertEqual(port.send.call_count,4)
        a.muted=False;a.probe_channel.get.return_value=17;a.send_probe_cc(0)
        self.assertEqual(port.send.call_count,4)

if __name__=='__main__':unittest.main()
