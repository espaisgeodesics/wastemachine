from copy import deepcopy
from math import nan,inf
import unittest
from atmo_presence_fade import PresenceFades,settings,validate,FUNCTION
from experience_rules import RulesConfig,ExperienceRule,RuleAction


def card(channel=1,**fade):
    return dict(function=FUNCTION,channel=channel,cc=119,mute_audible=0,mute_silent=127,mute_fade=dict(enabled=True,cc=118,in_s=2.,out_s=3.,level=100,**fade))


class FadeTests(unittest.TestCase):
    def setUp(self):
        self.sent=[];self.card=card();self.fade=PresenceFades(lambda *msg:self.sent.append(msg))
    def enter(self,t=0):return self.fade.request(0,self.card,True,t)
    def leave(self,t):return self.fade.request(0,self.card,False,t)
    def test_gain_is_zero_before_unmute_and_entry_is_progressive(self):
        self.enter()
        self.assertEqual(self.sent,[(1,118,0),(1,119,0)])
        for i in range(1,61):self.fade.tick(i/30)
        levels=[v for ch,cc,v in self.sent if cc==118]
        self.assertEqual(levels,sorted(set(levels)))
        self.assertEqual(levels[-1],100)
        self.assertTrue(any(40<=v<=60 for v in levels))
        self.assertTrue(all(cc in (118,119) for ch,cc,v in self.sent))
    def test_exit_sends_zero_before_mute_and_never_touches_notes_or_transport(self):
        self.enter();self.fade.tick(2);self.sent.clear();self.leave(3)
        self.fade.tick(4.5)
        self.assertIn((1,118,50),self.sent)
        self.assertNotIn((1,119,127),self.sent)
        self.fade.tick(6)
        self.assertEqual(self.sent[-2:],[(1,118,0),(1,119,127)])
        previous=list(self.sent)
        for i in range(10):self.fade.tick(7+i)
        self.assertEqual(self.sent,previous)
    def test_reentry_mid_exit_reverses_without_resetting_volume(self):
        self.enter();self.fade.tick(2);self.leave(3);self.fade.tick(4.5)
        self.assertEqual(self.sent[-1],(1,118,50))
        self.sent.clear();self.enter(4.5);self.fade.tick(5);self.fade.tick(5.5)
        self.assertNotIn((1,118,0),self.sent)
        self.assertNotIn((1,119,127),self.sent)
        self.assertEqual(self.sent[-1],(1,118,100))
    def test_removal_during_entry_fades_from_current_level(self):
        self.enter();self.fade.tick(1);self.leave(1)
        self.assertEqual(self.fade.states[0].start,50)
        self.fade.tick(1.75);self.assertEqual(self.sent[-1],(1,118,25))
        self.fade.tick(2.5);self.assertEqual(self.sent[-1],(1,119,127))
    def test_repeated_detection_does_not_restart_or_flood(self):
        for i in range(1001):self.enter(i/500)
        self.assertEqual(self.sent[-1],(1,118,100))
        self.assertLessEqual(len(self.sent),64)
    def test_independent_cards_and_channels_have_separate_envelopes(self):
        self.enter();other=card(channel=2);other['mute_fade']['in_s']=4
        self.fade.request(1,other,True,0);self.fade.tick(2)
        self.assertIn((1,118,100),self.sent);self.assertIn((2,118,50),self.sent)
        self.leave(2);self.fade.tick(4)
        self.assertEqual(self.fade.states[1].level_sent,100)
        self.assertLess(self.fade.states[0].level_sent,100)
    def test_initial_absence_only_sends_silence_once(self):
        for i in range(20):self.leave(i)
        self.assertEqual(self.sent,[(1,118,0),(1,119,127)])
    def test_zero_durations_are_supported(self):
        self.card['mute_fade'].update(in_s=0,out_s=0)
        self.enter();self.assertEqual(self.sent,[(1,118,0),(1,119,0),(1,118,100)])
        self.leave(1);self.assertEqual(self.sent[-2:],[(1,118,0),(1,119,127)])
    def test_immediate_silence_cancels_future_unmute(self):
        self.enter();self.fade.tick(1)
        self.fade.request(0,self.card,True,1.1,immediate=True)
        self.assertEqual(self.sent[-2:],[(1,118,0),(1,119,127)])
        self.sent.clear();self.fade.tick(100)
        self.assertFalse(self.sent)
    def test_emergency_still_attempts_mute_when_zero_gain_send_fails(self):
        self.enter();self.fade.tick(2);self.sent.clear()
        original=self.fade.send
        def fail(ch,cc,value):
            if cc==118 and value==0:raise OSError('gain unavailable')
            return original(ch,cc,value)
        self.fade.send=fail
        self.assertFalse(self.fade.stop(0,3))
        self.assertEqual(self.sent,[(1,119,127)])
        self.assertEqual(self.fade.states[0].gate_sent,127)
    def test_reentry_after_partial_silence_failure_reprimes_zero_before_unmute(self):
        self.enter();self.fade.tick(2)
        original=self.fade.send
        def fail(ch,cc,value):
            if cc==118 and value==0:raise OSError('gain unavailable')
            return original(ch,cc,value)
        self.fade.send=fail;self.assertFalse(self.fade.stop(0,3))
        self.fade.send=original;self.sent.clear();self.enter(4)
        self.assertEqual(self.sent,[(1,118,0),(1,119,0)])

    def test_changed_route_is_silenced_before_new_route_unmutes(self):
        self.enter();self.fade.tick(2);self.sent.clear()
        other=card(channel=2)
        self.fade.request(0,other,True,3)
        self.assertEqual(self.sent,[(1,118,0),(1,119,127),(2,118,0),(2,119,0)])
    def test_failed_initial_gain_does_not_unmute_and_retries_current_presence(self):
        def send(ch,cc,value):
            if not self.sent:self.sent.append((ch,cc,value));raise OSError('port closed')
            self.sent.append((ch,cc,value))
        self.fade=PresenceFades(send)
        self.assertFalse(self.enter());self.assertNotIn((1,119,0),self.sent)
        self.leave(.1);self.fade.tick(.5)
        self.assertNotIn((1,119,0),self.sent)
        self.assertEqual(self.sent[-1],(1,119,127))
    def test_failed_final_gain_does_not_mute_before_receiver_accepts_zero(self):
        self.enter();self.fade.tick(2);self.leave(3)
        original=self.fade.send
        def fail(ch,cc,value):
            if cc==118 and value==0:raise OSError('unavailable')
            return original(ch,cc,value)
        self.fade.send=fail
        self.assertFalse(self.fade.tick(6));self.assertNotIn((1,119,127),self.sent)
        self.fade.send=original;self.fade.tick(6.5)
        self.assertEqual(self.sent[-2:],[(1,118,0),(1,119,127)])
    def test_stop_failure_prevents_new_route_from_unmuting(self):
        self.enter();self.fade.tick(2)
        def fail(*args):raise OSError('closed')
        self.fade.send=fail
        self.assertFalse(self.fade.request(0,card(channel=2),True,3))
        self.assertEqual(self.fade.states[0].route.channel,1)
    def test_clear_prevents_old_events_on_a_new_connection(self):
        self.enter();self.fade.tick(1);self.fade.stop(0,1.1);self.fade.clear();self.sent.clear()
        self.fade.tick(10);self.assertFalse(self.sent)
        self.enter(11);self.assertEqual(self.sent,[(1,118,0),(1,119,0)])
    def test_nonfinite_time_is_rejected(self):
        for value in (nan,inf):
            with self.assertRaises(ValueError):self.enter(value)
            with self.assertRaises(ValueError):self.fade.tick(value)


class FadeConfigTests(unittest.TestCase):
    def test_legacy_card_is_disabled_and_not_mutated(self):
        legacy=dict(function=FUNCTION,cc=119,channel=1);original=deepcopy(legacy)
        self.assertFalse(settings(legacy)['enabled']);validate([legacy]);self.assertEqual(legacy,original)
    def test_invalid_config_and_reserved_controls_are_rejected(self):
        for key,value in [('enabled',1),('in_s',-1),('out_s',61),('in_s',nan),('out_s',inf),('level',0),('cc',119),('cc',7),('cc',120),('unknown',5)]:
            with self.subTest(key=key,value=value):
                item=card();item['mute_fade'][key]=value
                with self.assertRaises(ValueError):settings(item)
    def test_same_cc_on_different_channels_is_allowed(self):
        self.assertEqual(validate([card(1),card(2)]),{(1,118):0,(2,118):1})
    def test_duplicate_fade_or_gate_or_other_controller_routes_are_rejected(self):
        for other in (card(),dict(function=FUNCTION,channel=1,cc=118),dict(function='Control MIDI CC',channel=1,cc=118),dict(function='Nota MIDI',channel=1,mixer=dict(channel=1,cc=118))):
            with self.subTest(other=other):
                with self.assertRaises(ValueError):validate([card(),other])
    def test_conflicting_xy_controller_is_rejected(self):
        other=dict(function='Chaos Oscillator (Kaoss XY)',channel=1,kaoss=dict(channel=1,mode='Efectes',x_cc=118,y_cc=17,rotation_enabled=False))
        with self.assertRaises(ValueError):validate([card(),other])
    def test_duplicate_gate_with_different_fade_cc_is_rejected(self):
        other=card();other['mute_fade']['cc']=117
        with self.assertRaises(ValueError):validate([card(),other])
    def test_mixer_route_uses_its_own_channel(self):
        other=dict(function='Nota MIDI',channel=2,mixer=dict(channel=1,cc=118))
        with self.assertRaises(ValueError):validate([card(),other])
    def test_rule_conflicts_with_fade_or_gate_are_rejected(self):
        from types import SimpleNamespace
        for cc in (118,119):
            rules=SimpleNamespace(rules=[SimpleNamespace(enabled=True,actions=[SimpleNamespace(kind='cc',channel=1,number=cc)])])
            with self.assertRaises(ValueError):validate([card()],rules)

    def test_disabled_fades_do_not_reserve_a_controller(self):
        item=card();item['mute_fade']['enabled']=False;item['cc']=117
        self.assertEqual(validate([item,card()]),{(1,118):1})

if __name__=='__main__':unittest.main()
