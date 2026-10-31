from dataclasses import FrozenInstanceError, replace
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock

import numpy as np
from PIL import Image
from domain_events import DomainEvent
from experience_rules import RuleAction, ExperienceRule, RulesConfig, RuleEngine, rebase_rule_images
from rule_outputs import RuleOutputs
from participants import ParticipantBinding, ParticipantRegistry
from participant_simulator import SimulatorSession
from spatial_zones import SpatialMap, Zone


def rule(rid='r', kind='color', value='#FF0000', **kwargs):
    action_options=kwargs.pop('action_options',{})
    return ExperienceRule(rid,rid,'zone_entered',(RuleAction(kind,value,duration_s=action_options.pop('duration_s',0),**action_options),),**kwargs)


def event(sequence=1,now=1,marker=0,**kwargs):
    return DomainEvent(sequence,now,kwargs.pop('kind','zone_entered'),'camera:0',marker_id=marker,zone_id='z',**kwargs)


class RuleModelTests(unittest.TestCase):
    def test_old_projects_empty_and_configuration_roundtrip_multiple_actions(self):
        self.assertFalse(RulesConfig.from_project({}).rules)
        r=replace(rule(),actions=(RuleAction('color','#AABBCC',duration_s=0),RuleAction('note',duration_s=.2)))
        config=RulesConfig((r,))
        self.assertEqual(RulesConfig.from_project({'experience_rules':config.to_dict()}),config)
        self.assertEqual(RulesConfig.from_project(json.loads(json.dumps({'experience_rules':config.to_dict()}))),config)
        with self.assertRaises(FrozenInstanceError):r.priority=99

    def test_invalid_action_types_values_and_untrusted_code_rejected(self):
        for kwargs in ({'kind':'exec','value':'print(1)'},{'kind':'color','value':'red'},
                       {'kind':'image','value':'a.py'},{'kind':'note','duration_s':0},
                       {'kind':'note','duration_s':61},{'kind':'note','channel':True},
                       {'kind':'cc','value':'128'},{'kind':'cc','value':'-1'},
                       {'duration_s':float('nan')},{'number':128}):
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):RuleAction(**kwargs)
        for block in (None,{},dict(schema_version=True,rules=[]),dict(schema_version=9,rules=[]),
                      dict(schema_version=1,rules=[{'rule_id':'r','actions':[{'kind':'exec'}]}])):
            with self.subTest(block=block),self.assertRaises(ValueError):RulesConfig.from_project({'experience_rules':block})

    def test_rule_limits_and_duplicate_ids(self):
        with self.assertRaises(ValueError):RulesConfig((rule(),rule()))
        with self.assertRaises(ValueError):RulesConfig(tuple(rule(str(i)) for i in range(129)))
        with self.assertRaises(ValueError):replace(rule(),actions=())
        with self.assertRaises(ValueError):replace(rule(),priority=0)
        with self.assertRaises(ValueError):replace(rule(),trigger='source_unavailable')

    def test_midi_channels_reserved_from_legacy_cards(self):
        config=RulesConfig((rule(kind='note',action_options={'duration_s':.2}),))
        config.validate_channels([{'function':'Nota MIDI','channel':1}])
        with self.assertRaises(ValueError):config.validate_channels([{'function':'Nota MIDI','channel':16}])
        RulesConfig((replace(config.rules[0],enabled=False),)).validate_channels([{'function':'Nota MIDI','channel':16}])
        config.validate_channels([{'function':'Cap acció','channel':16}])

    def test_combined_filters_and_exit_revalidation_default(self):
        r=replace(rule(),source_id='camera:0',marker_id=2,participant_id='p',zone_id='z')
        e=event(marker=2,participant_id='p')
        self.assertTrue(r.matches(e))
        for change in ({'source_id':'camera:1'},{'marker_id':3},{'participant_id':'q'},{'zone_id':'other'}):
            self.assertFalse(r.matches(replace(e,**change)))
        exit_rule=replace(r,trigger='zone_exited')
        self.assertFalse(exit_rule.matches(replace(e,kind='zone_exited',reason='detection_gap')))
        self.assertTrue(replace(exit_rule,reason='any').matches(replace(e,kind='zone_exited',reason='detection_gap')))

    def test_ordering_deduplication_and_retired_people(self):
        registry=ParticipantRegistry((ParticipantBinding('p','P','#FFFFFF','camera:0',0),))
        engine=RuleEngine(RulesConfig((rule('low',priority=1),rule('high',priority=20))))
        batch=engine.consume((event(2,2),event(1,1)),registry)
        self.assertEqual([r.rule.rule_id for r in batch],['high','low','high','low'])
        self.assertFalse(engine.consume((event(1),event(2)),registry))
        registry.set_retired('p')
        self.assertFalse(engine.consume((event(3,3,participant_id='p'),),registry))

    def test_manual_named_rule_explicit_and_disabled_rule_no_output(self):
        engine=RuleEngine(RulesConfig((rule(source_id='camera:0',marker_id=2),)))
        requests=engine.manual('r',1)
        self.assertEqual(len(requests),1)
        self.assertEqual(requests[0].event.marker_id,2)
        self.assertFalse(RuleEngine(RulesConfig((replace(rule(),enabled=False),))).manual('r',1))

    def test_save_as_rebases_rule_assets_without_mutating_original(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp);old=root/'old'/'p.json';new=root/'new'/'p.json'
            config=RulesConfig((rule(kind='image',value='photo.png'),))
            rebased=rebase_rule_images(config,old,new)
            self.assertEqual(rebased.rules[0].actions[0].value,str(root/'old'/'photo.png'))
            self.assertEqual(config.rules[0].actions[0].value,'photo.png')
            with self.assertRaises(ValueError):rebase_rule_images(config,None,new)


class RuleOutputTests(unittest.TestCase):
    def setUp(self):
        self.outputs=RuleOutputs()

    def requests(self,*rules,evt=None):
        return RuleEngine(RulesConfig(rules)).consume((evt or event(),))

    def test_priority_persistent_ownership_expiry_and_return_to_previous_claim(self):
        low=rule('low',priority=1)
        high=rule('high',value='#00FF00',priority=90,action_options={'duration_s':.5})
        self.outputs.apply(self.requests(low,high),1)
        np.testing.assert_array_equal(self.outputs.frame((3,2))[0,0],[0,255,0])
        self.outputs.apply(self.requests(low,evt=event(2,1.1)),1.1)
        self.assertEqual(self.outputs.winner().request.rule.rule_id,'high')
        self.outputs.tick(1.6)
        self.assertEqual(self.outputs.winner().request.rule.rule_id,'low')
        self.outputs.tick(999)
        self.assertIsNotNone(self.outputs.frame((3,2)))

    def test_stable_ties_independent_of_rule_order_and_marker_order(self):
        for rules in ((rule('b'),rule('a',value='#0000FF')),(rule('a',value='#0000FF'),rule('b'))):
            outputs=RuleOutputs();outputs.apply(self.requests(*rules),1)
            self.assertEqual(outputs.winner().request.rule.rule_id,'a')
        outputs=RuleOutputs();r=rule()
        requests=RuleEngine(RulesConfig((r,))).consume((event(2,1,marker=4),event(1,1,marker=0)))
        outputs.apply(requests,1)
        self.assertEqual(outputs.winner().request.event.marker_id,0)

    def test_release_only_matching_group_and_marker_then_manual_clear(self):
        requests=RuleEngine(RulesConfig((rule(),))).consume((event(1,1,0),event(2,1,1)))
        self.outputs.apply(requests,1)
        release=replace(rule('exit',kind='release_visual',value=''),trigger='zone_exited')
        self.outputs.apply(self.requests(release,evt=replace(event(3,2,0),kind='zone_exited',reason='movement')),2)
        self.assertEqual(len(self.outputs.claims),1)
        self.assertEqual(self.outputs.winner().request.event.marker_id,1)
        self.outputs.clear_visuals();self.assertIsNone(self.outputs.frame((2,2)))

    def test_failed_image_preserves_previous_output_and_valid_image_fits(self):
        self.outputs.apply(self.requests(rule()),1)
        self.outputs.apply(self.requests(rule('image',kind='image',value='/missing/image.png',priority=100)),1)
        np.testing.assert_array_equal(self.outputs.frame((2,2))[0,0],[0,0,255])
        self.assertNotEqual(self.outputs.log[-1][3],'acceptada')
        with TemporaryDirectory() as tmp:
            image=Path(tmp)/'green.png';Image.new('RGB',(20,20),'lime').save(image)
            self.outputs.apply(self.requests(rule('image',kind='image',value=str(image),priority=100)),2)
            frame=self.outputs.frame((20,10))
            np.testing.assert_array_equal(frame[5,10],[0,255,0])
            np.testing.assert_array_equal(frame[5,0],[0,0,0])

    def test_shared_notes_release_only_when_last_owner_finishes(self):
        send=Mock(return_value=True)
        a=rule('a',kind='note',action_options={'duration_s':.2})
        b=rule('b',kind='note',action_options={'duration_s':.5})
        self.outputs.apply(self.requests(a,b),1,send)
        self.assertEqual([c.args[0].kind for c in send.call_args_list],['note_on'])
        self.outputs.tick(1.3,send)
        self.assertEqual(send.call_count,1)
        self.outputs.tick(1.6,send)
        self.assertEqual([c.args[0].kind for c in send.call_args_list],['note_on','note_off'])
        self.assertFalse(self.outputs.notes)

    def test_mute_no_port_or_failed_send_never_queue_deferred_note_on(self):
        requests=self.requests(rule(kind='note',action_options={'duration_s':.2}))
        for send,enabled in ((None,True),(Mock(return_value=True),False),(Mock(return_value=False),True),(Mock(side_effect=OSError('port')),True)):
            out=RuleOutputs();out.apply(requests,1,send,midi_enabled=enabled)
            self.assertFalse(out.notes)
            later=Mock();out.tick(2,later);later.assert_not_called()

    def test_failed_note_off_retries_and_stop_midi_releases_owned_channels_only(self):
        send=Mock(return_value=True)
        self.outputs.apply(self.requests(rule(kind='note',action_options={'duration_s':.1})),1,send)
        self.outputs.tick(1.2,Mock(side_effect=OSError('busy')))
        self.assertTrue(self.outputs.notes)
        self.outputs.tick(1.4,send)
        self.assertFalse(self.outputs.notes)
        self.outputs.stop_midi(send)
        self.assertEqual({c.args[0].channel for c in send.call_args_list},{16})
        self.assertEqual(send.call_args.args[0].kind,'cc')
        self.assertEqual(send.call_args.args[0].number,64)

    def test_cc_conflicts_resolved_by_priority_once_in_a_batch(self):
        high=rule('high',kind='cc',value='100',priority=100)
        low=rule('low',kind='cc',value='10',priority=1)
        send=Mock(return_value=True)
        self.outputs.apply(self.requests(low,high),1,send)
        self.assertEqual(send.call_count,1)
        self.assertEqual(send.call_args.args[0].value,100)

    def test_runtime_claim_and_diagnostic_memory_bounded(self):
        for i in range(270):self.outputs.apply(self.requests(rule(str(i),group=str(i))),1)
        self.assertEqual(len(self.outputs.claims),256)
        self.assertEqual(len(self.outputs.log),200)

    def test_active_image_resources_bounded_without_displacing_accepted_owner(self):
        with TemporaryDirectory() as tmp:
            for i in range(5):
                path=Path(tmp)/f'{i}.png';Image.new('RGB',(4,4),'red').save(path)
                self.outputs.apply(self.requests(rule(str(i),kind='image',value=str(path),group=str(i)),evt=event(i+1,i)),i)
            self.assertEqual(len(self.outputs.claims),4)
            self.assertEqual(self.outputs.winner().request.rule.rule_id,'3')
            self.assertIn('quatre',self.outputs.log[-1][3])

    def test_simulator_executes_shared_rules_without_real_ports(self):
        s=SimulatorSession();s.configure_spatial(SpatialMap(zones=(Zone('z','Bosc',{(2,2)},{0}),)))
        r=replace(rule(),actions=(RuleAction('color','#123456',duration_s=0),RuleAction('note',duration_s=.2),RuleAction('cc','99')))
        s.configure_rules(RulesConfig((r,)))
        s.set_pose('virtual-1',position=(.3,.3))
        for now in (0,.08,.16):s.advance(now)
        np.testing.assert_array_equal(s.rule_outputs.frame((2,2))[0,0],[0x56,0x34,0x12])
        self.assertEqual([c.kind for c in s.midi_commands],['note_on','cc'])
        s.advance(.4)
        self.assertEqual(s.midi_commands[-1].kind,'note_off')
        self.assertEqual(len([c for c in s.midi_commands if c.kind=='note_on']),1)


if __name__=='__main__':unittest.main()
