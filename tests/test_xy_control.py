from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

from atmo_xy_control import BusXY,State,MidiFXOutput,bus_profile,settings
from atmo_ambience import ambience_settings
from experience_rules import RulesConfig,RuleAction,ExperienceRule


def card():
    config,meta=bus_profile()
    return dict(function='Chaos Oscillator (Kaoss XY)',channel=16,kaoss=config.to_dict(),**meta)


class XYTests(unittest.TestCase):
    def setUp(self):
        self.card=card();self.sent=[]
        self.bus=BusXY(lambda *args:self.sent.append(args) or True)
        self.bus.configure(BusXY.validate([self.card],RulesConfig()))
    def observe(self,x,y,t=1):self.bus.observe(0,x,y,0,t);self.bus.tick(t)
    def test_effect_profile_never_uses_volume_or_rotation(self):
        self.observe(0,1)
        self.assertEqual(self.sent,[('ATMO FX',16,16,0),('ATMO FX',16,17,0)])
        self.assertFalse(self.card['kaoss']['rotation_enabled'])
    def test_cadence_and_deduplication(self):
        self.observe(0,1)
        for i in range(1,30):
            self.bus.observe(0,0,1,0,1+i/100);self.bus.tick(1+i/100)
        self.assertEqual(len(self.sent),2)
    def test_rate_limit_under_fast_motion(self):
        for i in range(100):
            self.bus.observe(0,i/100,i/100,0,1+i/1000);self.bus.tick(1+i/1000)
        self.assertLessEqual(len(self.sent),6)
    def test_inversion_ranges_and_smoothing(self):
        self.bus.cards[0]['kaoss_ranges']['x']=[20,100]
        self.observe(0,0)
        self.assertIn(('ATMO FX',16,16,20),self.sent)
        self.assertIn(('ATMO FX',16,17,127),self.sent)
        self.bus.observe(0,1,1,0,1.04);self.bus.tick(1.04)
        self.assertTrue(20<self.sent[-2][-1]<100)
    def test_progressive_release_and_completion(self):
        self.observe(0,0)
        self.bus.release(0,1.1)
        self.bus.tick(1.4)
        self.assertLessEqual(abs(self.sent[-2][-1]-63.5),.5)
        self.assertLessEqual(abs(self.sent[-1][-1]-63.5),.5)
        self.bus.tick(1.8)
        self.assertEqual(self.sent[-2:],[('ATMO FX',16,16,127),('ATMO FX',16,17,0)])
        self.assertFalse(self.bus.states)
    def test_reentry_cancels_return(self):
        self.observe(0,0);self.bus.release(0,1.1);self.bus.tick(1.2)
        self.bus.observe(0,.4,.4,0,1.3);self.bus.tick(1.3)
        self.assertIsNone(self.bus.states[0].release_at)
    def test_timeout_releases_without_new_camera_observations(self):
        self.observe(0,0);self.bus.tick(1.3);self.bus.tick(2)
        self.assertFalse(self.bus.states)
    def test_hold_is_retained_until_stop(self):
        self.bus.cards[0]['kaoss_release']='hold';self.observe(0,0)
        self.bus.tick(2);self.bus.tick(3);self.assertEqual(len(self.sent),2)
        self.assertTrue(self.bus.stop());self.assertEqual(len(self.sent),4)
    def test_manual_test_literal_and_owned_by_panic(self):
        self.bus.test(0,'x',64);self.bus.test(0,'y',64)
        self.assertEqual(self.sent[-2:],[('ATMO FX',16,16,64),('ATMO FX',16,17,64)])
        self.bus.stop();self.assertEqual(self.sent[-2:],[('ATMO FX',16,16,127),('ATMO FX',16,17,0)])
    def test_failed_send_drops_stale_work(self):
        self.bus.send=lambda *args:False;self.observe(.5,.5)
        self.assertFalse(self.bus.states)
        sent=[];self.bus.send=lambda *args:sent.append(args)
        self.bus.tick(2);self.assertFalse(sent)
    def test_legacy_project_and_disabling_dedicated_mode(self):
        legacy=card();legacy.pop('kaoss_bus')
        self.assertIsNone(settings(legacy))
        self.assertNotIn('kaoss_bus',ambience_settings(legacy))
        disabled=card();disabled['kaoss_bus']=None
        self.assertIsNone(ambience_settings(disabled)['kaoss_bus'])
    def test_reserved_cc_and_duplicate_route_rejected(self):
        for cc in (0,7,11,64,98,101,121):
            c=card();c['kaoss']['x_cc']=cc
            with self.assertRaises(ValueError):settings(c)
        with self.assertRaises(ValueError):BusXY.validate([card(),card()],RulesConfig())
    def test_other_card_and_rule_conflict_rejected(self):
        other=dict(function='Control MIDI CC',channel=16,cc=16)
        with self.assertRaises(ValueError):BusXY.validate([card(),other],RulesConfig())
        rule=ExperienceRule('c','CC','manual',(RuleAction('cc',value='64',channel=16,number=17),))
        with self.assertRaises(ValueError):BusXY.validate([card()],RulesConfig((rule,)))
    def test_unknown_port_fields_and_invalid_numbers_rejected(self):
        for values in ({'rate_hz':float('nan')},{'return_s':-1},{'port':None},{'extra':1}):
            c=card();c['kaoss_bus'].update(values)
            with self.assertRaises(ValueError):settings(c)


class PortTests(unittest.TestCase):
    def test_disconnect_does_not_reopen_until_explicit_reconnect(self):
        port=Mock();mido=SimpleNamespace(Message=lambda *args,**kwargs:kwargs,get_output_names=lambda:['ATMO FX'],open_output=Mock(return_value=port))
        sink=MidiFXOutput(SimpleNamespace(midi=None))
        with patch.dict('sys.modules',mido=mido):
            self.assertTrue(sink.send('ATMO FX',16,16,64))
            port.send.side_effect=OSError('removed')
            self.assertFalse(sink.send('ATMO FX',16,17,64))
            self.assertFalse(sink.send('ATMO FX',16,17,64));self.assertEqual(mido.open_output.call_count,1)
            sink.reconnect();port.send.side_effect=None
            self.assertTrue(sink.send('ATMO FX',16,17,64));self.assertEqual(mido.open_output.call_count,2)
        sink.close()
    def test_shared_main_port_is_not_closed(self):
        port=Mock();sink=MidiFXOutput(SimpleNamespace(midi=port))
        with patch.dict('sys.modules',mido=SimpleNamespace(Message=lambda *a,**kw:kw)):
            self.assertTrue(sink.send('',16,16,10))
        sink.close();port.close.assert_not_called()


if __name__=='__main__':unittest.main()
