import copy
import json
import math
import unittest
from dataclasses import replace
from kaoss_xy import KaossConfig, KaossEngine, PRESETS, preset, pack_configs, unpack_configs, validate_assignments
from participant_simulator import SimulatorSession
from experience_rules import RulesConfig, ExperienceRule, RuleAction


class KaossTests(unittest.TestCase):
    def engine(self, config=None):
        self.commands = []
        return KaossEngine({0: config or replace(preset('ATMOSFERA'), smoothing_s=0, deadzone=0)})

    def feed(self, engine, x=.5, y=.5, rotation=0, now=1):
        engine.observe(0, x, y, rotation, now);engine.tick(now, self.commands.append)

    def test_four_required_presets(self):
        configs = [preset(name) for name in PRESETS]
        self.assertEqual([c.mode for c in configs], ['Instrument', 'Instrument', 'Efectes', 'Efectes'])
        self.assertEqual([(c.x_cc,c.y_cc,c.rotation_cc) for c in configs[2:]], [(74,1,11),(10,11,1)])
        self.assertTrue(configs[1].y_velocity);self.assertEqual(configs[1].rotation_cc,74)

    def test_all_presets_roundtrip_with_custom_settings(self):
        for name in PRESETS:
            config = replace(preset(name), rotation_enabled=False, channel=8, root=0, quantize_beats=.25)
            self.assertEqual(unpack_configs(json.loads(json.dumps(pack_configs({49: config})))), {49: config})

    def test_validation_rejects_bad_numbers_and_modes(self):
        cases = [('channel',True), ('channel',0), ('channel',17), ('root',12), ('root',1.2),
                 ('velocity',0), ('note_min',128), ('note_max',-1), ('smoothing_s',math.nan),
                 ('deadzone',math.inf), ('deadzone',True), ('quantize_beats',.3), ('lost_timeout_s',0),
                 ('mode','unknown'), ('scale','unknown'), ('rotation_enabled',1), ('x_cc',120)]
        for key, value in cases:
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):replace(KaossConfig(), **{key:value})
        with self.assertRaises(ValueError):replace(KaossConfig(), note_min=1,note_max=1, root=0,scale='Pentatònica major')

    def test_active_ccs_unique_and_no_hold_pedals(self):
        for cc in (64,66,69,120,127):
            with self.assertRaises(ValueError):replace(KaossConfig(),y_cc=cc)
        with self.assertRaises(ValueError):replace(KaossConfig(),rotation_cc=74)
        replace(KaossConfig(),rotation_cc=74,rotation_enabled=False)
        replace(preset('PULSACIÓ'),y_cc=74)  # Y is velocity, not CC

    def test_channel_reservation_and_bounded_assignments(self):
        with self.assertRaises(ValueError):validate_assignments({0:KaossConfig(),1:KaossConfig()})
        with self.assertRaises(ValueError):validate_assignments({0:KaossConfig()}, {2})
        for marker in (True,-1,50,'0'):
            with self.assertRaises(ValueError):validate_assignments({marker:KaossConfig()})
        with self.assertRaises(ValueError):validate_assignments({i:KaossConfig(channel=i%16+1) for i in range(17)})

    def test_invalid_file_not_silently_coerced(self):
        valid=pack_configs({0:KaossConfig()})
        bad=[None, {}, dict(valid,schema_version=True),dict(valid,schema_version=2),dict(valid,extra=1),
             dict(valid,kaoss_xy=[]),dict(valid,kaoss_xy={'00':{}}),dict(valid,kaoss_xy={'-1':{}}),
             dict(valid,kaoss_xy={'0':{'extra':1}})]
        for data in bad:
            with self.subTest(data=data),self.assertRaises(ValueError):unpack_configs(data)

    def test_instrument_edges_scale_and_off_before_on(self):
        config=replace(KaossConfig(),smoothing_s=0,deadzone=0)
        engine=self.engine(config)
        self.feed(engine,x=0);self.feed(engine,x=1,now=1.1)
        notes=[c for c in self.commands if c.kind.startswith('note')]
        self.assertEqual([(c.kind,c.number) for c in notes], [('note_on',config.pitches()[0]),('note_off',config.pitches()[0]),('note_on',config.pitches()[-1])])
        self.assertTrue(all(c.channel==2 for c in self.commands))

    def test_effects_never_send_notes_and_exact_mapping(self):
        engine=self.engine(replace(preset('ÒRBITA'),smoothing_s=0))
        self.feed(engine,x=0,y=0,rotation=.5)
        self.assertEqual([(c.kind,c.number,c.value) for c in self.commands], [('cc',10,0),('cc',11,127),('cc',1,64)])
        self.commands.clear();engine.tick(1.03,self.commands.append);self.assertEqual(self.commands,[])

    def test_velocity_changes_do_not_retrigger_same_pitch(self):
        engine=self.engine(replace(preset('PULSACIÓ'),smoothing_s=0))
        self.feed(engine,y=1);self.feed(engine,y=0,now=1.1)
        notes=[c for c in self.commands if c.kind=='note_on']
        self.assertEqual(len(notes),1);self.assertEqual(notes[0].value,1)
        self.feed(engine,x=1,y=0,now=1.2)
        self.assertEqual([c.value for c in self.commands if c.kind=='note_on'],[1,127])
        self.assertNotIn(74,[c.number for c in self.commands if c.kind=='cc' and c.value==127])

    def test_cc_rate_limit_and_failed_send_retry(self):
        engine=self.engine(replace(preset('TRANSFORMACIÓ'),smoothing_s=0,deadzone=0))
        self.feed(engine,x=0);self.commands.clear()
        engine.observe(0,1,0,.5,1.005);engine.tick(1.005,self.commands.append)
        self.assertEqual(self.commands,[])
        engine.tick(1.025,lambda c:False)
        engine.tick(1.05,self.commands.append)
        self.assertEqual(len(self.commands),3)

    def test_smoothing_deadzone_and_rotation_wrap(self):
        engine=self.engine(replace(preset('TRANSFORMACIÓ'),smoothing_s=1,deadzone=.02))
        self.feed(engine,x=.5,rotation=.99)
        engine.observe(0,.51,.5,.01,1.1)
        self.assertEqual(engine.voices[0].filtered[0],.5)
        self.assertGreater(engine.voices[0].filtered[2],.99)
        engine.observe(0,1,.5,.03,1.2)
        self.assertGreater(engine.voices[0].filtered[0],.5)
        self.assertLess(engine.voices[0].filtered[0],.6)

    def test_rotation_disabled_and_inversions(self):
        engine=self.engine(replace(preset('ÒRBITA'),rotation_enabled=False,invert_x=True,invert_y=False,smoothing_s=0))
        self.feed(engine,x=0,y=1,rotation=.5)
        self.assertEqual([(c.number,c.value) for c in self.commands],[(10,127),(11,127)])

    def test_quantization_coalesces_latest_pitch_and_does_not_postpone(self):
        engine=self.engine(replace(KaossConfig(),quantize_beats=1,smoothing_s=0,deadzone=0,lost_timeout_s=1))
        self.feed(engine,x=0,now=1.1)
        self.assertFalse(any(c.kind=='note_on' for c in self.commands))
        self.feed(engine,x=1,now=1.4)
        engine.tick(1.5,self.commands.append)
        notes=[c for c in self.commands if c.kind=='note_on']
        self.assertEqual([c.number for c in notes],[engine.configs[0].pitches()[-1]])

    def test_disappearance_cancels_pending_note_before_quantized_boundary(self):
        engine=self.engine(replace(KaossConfig(),quantize_beats=1,lost_timeout_s=.1))
        self.feed(engine,now=1.1);engine.tick(1.5,self.commands.append)
        self.assertFalse(any(c.kind=='note_on' for c in self.commands));self.assertEqual(engine.voices,{})

    def test_loss_releases_once_then_reappearance_can_play(self):
        engine=self.engine();self.feed(engine)
        engine.tick(1.249,self.commands.append);self.assertEqual(len(engine.voices),1)
        engine.tick(1.25,self.commands.append);engine.tick(2,self.commands.append)
        self.assertEqual([c.kind for c in self.commands if c.kind.startswith('note')],['note_on','note_off'])
        self.feed(engine,now=2.1)
        self.assertEqual(len([c for c in self.commands if c.kind=='note_on']),2)

    def test_failed_off_blocks_replacement_and_retries(self):
        engine=self.engine();self.feed(engine,x=0)
        engine.observe(0,1,.5,0,1.1)
        attempts=[]
        def fail(c):attempts.append(c);return False
        engine.tick(1.1,fail)
        self.assertEqual([c.kind for c in attempts],['note_off'])
        engine.tick(1.12,self.commands.append)
        self.assertEqual([c.kind for c in self.commands[-2:]],['note_off','note_on'])

    def test_failed_on_not_replayed_without_fresh_observation(self):
        engine=self.engine();engine.observe(0,.5,.5,0,1)
        engine.tick(1,lambda c:False);self.commands.clear()
        engine.tick(1.1,self.commands.append)
        self.assertFalse(any(c.kind=='note_on' for c in self.commands))
        self.feed(engine,now=1.15)
        self.assertTrue(any(c.kind=='note_on' for c in self.commands))

    def test_stop_cancels_pending_and_failed_off_owns_until_retry(self):
        engine=self.engine();self.feed(engine)
        self.assertFalse(engine.stop(lambda c:False))
        engine.tick(1.1,self.commands.append)
        self.assertEqual(self.commands[-1].kind,'note_off');self.assertEqual(engine.voices,{})
        engine.tick(1.2,self.commands.append)
        self.assertEqual(len([c for c in self.commands if c.kind=='note_on']),1)

    def test_invalid_input_leaves_state_unchanged(self):
        engine=self.engine();self.feed(engine)
        before=copy.deepcopy(engine.voices)
        for args in [(0,math.nan,0,0,1.1),(0,0,0,0,.9),(0,0,2,0,1.1),(0,0,0,0,True)]:
            with self.assertRaises(ValueError):engine.observe(*args)
            self.assertEqual(engine.voices,before)
        with self.assertRaises(ValueError):engine.tick(1.1,self.commands.append,bpm=0)


class KaossSimulatorTests(unittest.TestCase):
    def test_five_people_independent_channels_and_source_loss(self):
        session=SimulatorSession();session.configure_kaoss({i:preset('ATMOSFERA',i+2) for i in range(5)})
        session.advance(1)
        self.assertEqual({c.channel for c in session.midi_commands if c.kind=='note_on'},set(range(2,7)))
        session.available=False;session.advance(1.1);session.advance(1.3)
        self.assertEqual(len([c for c in session.midi_commands if c.kind=='note_off']),5)
        self.assertEqual(session.kaoss.voices,{})

    def test_retirement_and_reset_preserve_configs_not_notes(self):
        session=SimulatorSession();session.configure_kaoss({0:KaossConfig()});session.advance(1)
        session.set_retired('virtual-1',True,1.1);session.advance(1.3)
        self.assertEqual(session.kaoss.voices,{})
        configs=dict(session.kaoss.configs);session.reset()
        self.assertEqual(session.kaoss.configs,configs);self.assertEqual(session.kaoss.voices,{})

    def test_reservation_conflict_is_atomic_in_both_directions(self):
        session=SimulatorSession();session.configure_kaoss({0:KaossConfig()});session.advance(1)
        rule=ExperienceRule('test','Test','manual',(RuleAction('note',channel=2),))
        rules=RulesConfig((rule,))
        with self.assertRaises(ValueError):session.configure_rules(rules)
        self.assertEqual(session.rule_engine.config,RulesConfig());self.assertEqual(len(session.kaoss.voices),1)
        session.configure_kaoss({});session.configure_rules(rules)
        with self.assertRaises(ValueError):session.configure_kaoss({0:KaossConfig()})
        self.assertEqual(session.kaoss.configs,{})

    def test_config_copied_and_reconfiguration_releases_owned_notes(self):
        session=SimulatorSession();configs={0:KaossConfig()};session.configure_kaoss(configs);configs.clear()
        session.advance(1);session.configure_kaoss({0:preset('ÒRBITA')})
        self.assertEqual(session.midi_commands[-1].kind,'note_off');self.assertEqual(session.kaoss.voices,{})
