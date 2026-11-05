from dataclasses import replace
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from bosc_viu import create_bosc_viu
from domain_events import DomainEvent
from experience_rules import ExperienceRule,RuleAction,RulesConfig,RuleEngine,rebase_rule_images
from local_audio import inspect_clip
from participant_simulator import SimulatorSession
from participants import ParticipantRegistry
from rule_outputs import RuleOutputs
from spatial_zones import SpatialMap


class BoscPrototypeTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.cards=[{'function':'Nota MIDI','channel':1,'note':36+i} for i in range(16)]
        self.path=create_bosc_viu(Path(self.temp.name)/'bosc',self.cards)
        self.data=json.loads(self.path.read_text(encoding='utf-8'))

    def session(self):
        s=SimulatorSession();s.configure_spatial(SpatialMap.from_project(self.data))
        s.configure_rules(RulesConfig.from_project(self.data),self.path)
        return s

    def test_demo_self_contained_valid_and_no_physical_calibration_or_midi_added(self):
        spatial=SpatialMap.from_project(self.data);rules=RulesConfig.from_project(self.data)
        self.assertEqual(len(spatial.zones),5);self.assertIsNone(spatial.calibration)
        self.assertEqual(len(ParticipantRegistry.from_project(self.data).snapshot()),5)
        self.assertTrue(all(c['function']=='Cap acció' for c in self.data['cards']))
        self.assertTrue(all(c['function']=='Nota MIDI' for c in self.cards))
        self.assertFalse(any(a.kind in ('note','cc') for r in rules.rules for a in r.actions))
        for r in rules.rules:
            for a in r.actions:
                if a.kind=='play_sound':self.assertLessEqual(inspect_clip(self.path.parent/a.value)[2],3.)
        self.assertEqual(self.data['experience_rules']['schema_version'],2)

    def test_demo_deterministic_and_never_overwrites_existing_folder(self):
        copy=create_bosc_viu(Path(self.temp.name)/'copy',self.cards)
        for sound in (self.path.parent/'sons').glob('*.wav'):
            self.assertEqual(sound.read_bytes(),(copy.parent/'sons'/sound.name).read_bytes())
        before=self.path.read_bytes()
        with self.assertRaises(FileExistsError):create_bosc_viu(self.path.parent,self.cards)
        self.assertEqual(self.path.read_bytes(),before)

    def test_virtual_five_people_enter_zones_audio_layers_and_clearing_color(self):
        s=self.session()
        for now in (0,.1,.2):s.advance(now)
        groups={voice.group for voice in s.audio.snapshot()}
        self.assertTrue({'ocells','riu','vent'}.issubset(groups))
        self.assertEqual(s.rule_outputs.winner().request.rule.rule_id,'clariana-enter')
        self.assertFalse(s.midi_commands)
        s.advance(.7)
        self.assertTrue(any(voice.gain>0 for voice in s.audio.snapshot()))

    def test_alarm_stops_birds_reduces_wind_and_manual_recovery_restores_bus(self):
        s=self.session()
        for now in (0,.1,.2):s.advance(now)
        s.set_pose('virtual-2',position=(.5,.5))
        for now in (.3,.4,.5,.7):s.advance(now)
        self.assertEqual(s.rule_outputs.winner().request.rule.rule_id,'alarma-enter')
        self.assertFalse(any(v.group=='ocells' for v in s.audio.snapshot()))
        self.assertEqual(s.audio.group_gain('ocells',.7),0)
        self.assertTrue(any(v.group=='alarma' for v in s.audio.snapshot()))
        s.manual_rule('restore',.8);s.advance(1.4)
        self.assertFalse(any(v.group=='alarma' for v in s.audio.snapshot()))
        self.assertAlmostEqual(s.audio.group_gain('ocells',1.4),1)
        self.assertEqual(s.rule_outputs.winner().request.rule.rule_id,'clariana-enter')

    def test_zone_exit_fades_only_that_participants_river_voice(self):
        s=self.session()
        s.set_pose('virtual-1',position=(.7,.4))
        for now in (0,.1,.2):s.advance(now)
        self.assertEqual(len([v for v in s.audio.snapshot() if v.group=='riu']),2)
        s.set_pose('virtual-1',position=(.1,.5))
        for now in (.3,.4,.6,1.2):s.advance(now)
        self.assertEqual([v.marker_id for v in s.audio.snapshot() if v.group=='riu'],[2])

    def test_manual_ambience_has_two_independent_loops_and_reset_clears_voices(self):
        s=self.session();s.manual_rule('ambient',0);s.advance(.7)
        self.assertTrue({'vent','fulles'}.issubset({v.group for v in s.audio.snapshot()}))
        s.reset();self.assertFalse(s.audio.snapshot());self.assertFalse(s.audio_commands)
        self.assertTrue(s.rule_engine.config.rules)


class AudioRuleSchemaTests(unittest.TestCase):
    def test_schema_one_unchanged_and_schema_two_roundtrip(self):
        plain=RulesConfig((ExperienceRule('r','R','manual',(RuleAction(),)),))
        self.assertEqual(plain.to_dict()['schema_version'],1)
        self.assertNotIn('gain',plain.to_dict()['rules'][0]['actions'][0])
        audio=replace(plain.rules[0],actions=(RuleAction('play_sound','a.wav',gain=.5,loop=True),))
        data=RulesConfig((audio,)).to_dict();self.assertEqual(data['schema_version'],2)
        self.assertEqual(RulesConfig.from_project({'experience_rules':data}),RulesConfig((audio,)))
        data['schema_version']=1
        with self.assertRaises(ValueError):RulesConfig.from_project({'experience_rules':data})
        for kwargs in ({'gain':float('nan')},{'fade_s':11},{'loop':'true'},{'audio_scope':'all'},{'value':'a.mp3'}):
            values=dict(kind='play_sound',value='a.wav');values.update(kwargs)
            with self.assertRaises(ValueError):RuleAction(**values)

    def test_audio_file_save_as_preserves_original_identity(self):
        config=RulesConfig((ExperienceRule('r','R','manual',(RuleAction('play_sound','sons/a.wav'),)),))
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            rebased=rebase_rule_images(config,root/'old'/'p.json',root/'new'/'p.json')
            self.assertEqual(rebased.rules[0].actions[0].value,str(root/'old'/'sons'/'a.wav'))
            self.assertEqual(config.rules[0].actions[0].value,'sons/a.wav')

    def test_audio_disabled_or_muted_does_not_defer_actions_but_visuals_work(self):
        from unittest.mock import Mock
        rule=ExperienceRule('r','R','manual',(RuleAction('color','#ABCDEF'),RuleAction('play_sound','a.wav')))
        requests=RuleEngine(RulesConfig((rule,))).manual('r',0)
        for callback,enabled in ((None,True),(Mock(return_value=False),True),(Mock(return_value=True),False)):
            outputs=RuleOutputs();outputs.apply(requests,0,project_file='/tmp/p.json',audio=callback,midi_enabled=enabled)
            self.assertIsNotNone(outputs.winner())
            self.assertNotEqual(outputs.log[-1][3],'en cua d’àudio')
            if callback is not None and not enabled:callback.assert_not_called()

    def test_priority_stop_suppresses_lower_priority_play_in_same_batch(self):
        from unittest.mock import Mock
        low=ExperienceRule('bird','Bird','zone_entered',(RuleAction('play_sound','a.wav',audio_group='birds'),),priority=1)
        high=ExperienceRule('alarm','Alarm','zone_entered',(RuleAction('stop_sound',audio_group='birds',audio_scope='group'),),priority=100)
        event=DomainEvent(1,0,'zone_entered','camera:0',marker_id=0)
        requests=RuleEngine(RulesConfig((low,high))).consume((event,))
        callback=Mock(return_value=True);outputs=RuleOutputs()
        outputs.apply(requests,0,project_file='/tmp/p.json',audio=callback)
        self.assertEqual([call.args[0].kind for call in callback.call_args_list],['stop_sound'])

    def test_same_owner_competing_plays_choose_high_priority_once(self):
        from unittest.mock import Mock
        low=ExperienceRule('low','Low','manual',(RuleAction('play_sound','low.wav'),),priority=1)
        high=ExperienceRule('high','High','manual',(RuleAction('play_sound','high.wav'),),priority=100)
        event=DomainEvent(1,0,'manual','operator')
        requests=RuleEngine(RulesConfig((low,high))).consume((event,))
        callback=Mock(return_value=True);outputs=RuleOutputs()
        outputs.apply(requests,0,project_file='/tmp/p.json',audio=callback)
        self.assertEqual(callback.call_count,1)
        self.assertEqual(Path(callback.call_args.args[0].path).name,'high.wav')


if __name__=='__main__':unittest.main()
