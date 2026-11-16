import ast
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import json
import math
import time
import unittest
from unittest.mock import Mock, patch

from atmo_card_functions import CHAOS_FUNCTION, LiveKaoss, live_configs, default_config, CardKaossEditor
from kaoss_xy import KaossConfig
from experience_rules import RulesConfig, RuleAction, ExperienceRule


ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'atmo_esfera_fx_4_5_15_pas_15_editor_musical_desplegable.py'


def method(name):
    tree=ast.parse(SOURCE.read_text(encoding='utf-8'))
    app=next(node for node in tree.body if isinstance(node,ast.ClassDef) and node.name=='App')
    function=next(node for node in app.body if isinstance(node,ast.FunctionDef) and node.name==name)
    scope={'CHAOS_FUNCTION':CHAOS_FUNCTION,'ZONE_FUNCTION':'Activar zona espacial',
           'MUTE_FUNCTION':'Control d’àudio / Mute','time':time,'CARD_LOST_TIMEOUT':.25,
           'math':math,'config_replace':replace,'default_config':default_config,
           'NOTE_NAMES':['Do','Do#','Re','Re#','Mi','Fa','Fa#','Sol','Sol#','La','La#','Si'],
           'NAMES':['visual'],'messagebox':Mock()}
    exec(compile(ast.Module(body=[function],type_ignores=[]),str(SOURCE),'exec'),scope)
    return scope[name]


def card(config=None):
    config=config or KaossConfig()
    return {'function':CHAOS_FUNCTION,'channel':config.channel,'kaoss':config.to_dict(),
            'axis':'Horitzontal','visual':0}


class LiveTests(unittest.TestCase):
    def live(self, config=None):
        app=SimpleNamespace(muted=False,bpm=120,send_rule_midi=Mock(return_value=True))
        live=LiveKaoss(app)
        live.configure([card(config)],RulesConfig())
        return live,app

    def test_real_xy_engine_emits_to_app_sink_and_releases_on_removal(self):
        live,app=self.live();live.observe(0,.5,.5,0);live.tick()
        self.assertTrue(any(c.args[0].kind=='note_on' for c in app.send_rule_midi.call_args_list))
        live.release(0)
        self.assertTrue(any(c.args[0].kind=='note_off' for c in app.send_rule_midi.call_args_list))
        self.assertFalse(live.engine.voices)

    def test_presence_timeout_continues_without_camera_observations(self):
        live,app=self.live(KaossConfig(lost_timeout_s=.1))
        with patch('atmo_card_functions.time.monotonic',return_value=1):live.observe(0,.5,.5,0);live.tick()
        with patch('atmo_card_functions.time.monotonic',return_value=1.2):live.tick()
        self.assertFalse(live.engine.voices)
        self.assertTrue(any(c.args[0].kind=='note_off' for c in app.send_rule_midi.call_args_list))

    def test_panic_stops_notes_and_does_not_create_new_notes(self):
        live,app=self.live();live.observe(0,.5,.5,0);live.tick()
        app.muted=True;live.stop();app.send_rule_midi.reset_mock()
        live.observe(0,.9,.9,0);live.tick()
        self.assertFalse(live.engine.voices);app.send_rule_midi.assert_not_called()

    def test_failed_noteoff_blocks_reconfiguration_without_losing_owner(self):
        live,app=self.live();live.observe(0,.5,.5,0);live.tick()
        app.send_rule_midi.return_value=False
        with self.assertRaises(ValueError):live.prepare([card(KaossConfig(channel=3))],RulesConfig())
        self.assertEqual(live.engine.configs[0].channel,2)
        self.assertIsNotNone(live.engine.voices[0].playing)
        app.send_rule_midi.return_value=True;live.configure([card(KaossConfig(channel=3))],RulesConfig())
        self.assertEqual(live.engine.configs[0].channel,3);self.assertFalse(live.engine.voices)

    def test_missing_port_does_not_queue_notes_for_future_connection(self):
        live,app=self.live();app.send_rule_midi.return_value=False
        live.observe(0,.5,.5,0);live.tick()
        app.send_rule_midi.return_value=True;app.send_rule_midi.reset_mock();live.tick()
        self.assertFalse(any(c.args[0].kind=='note_on' for c in app.send_rule_midi.call_args_list))
        live.observe(0,.5,.5,0);live.tick()
        self.assertTrue(any(c.args[0].kind=='note_on' for c in app.send_rule_midi.call_args_list))

    def test_project_card_json_roundtrip_preserves_every_parameter(self):
        config=KaossConfig(channel=3,root=2,scale='Major',note_min=50,note_max=80,
                           invert_x=True,smoothing_s=.2,quantize_beats=.5)
        cards=json.loads(json.dumps([card(config)]))
        self.assertEqual(live_configs(cards,RulesConfig())[0],config)
        self.assertEqual(live_configs([{'function':'Nota MIDI','channel':1}],RulesConfig()),{})

    def test_channels_cannot_overlap_legacy_cards_or_other_chaos(self):
        for cards in ([card(),{'function':'Nota MIDI','channel':2}], [card(),card()]):
            with self.assertRaises(ValueError):live_configs(cards,RulesConfig())
        with self.assertRaises(ValueError):live_configs([dict(card(),channel=3)],RulesConfig())

    def test_default_uses_free_channel(self):
        app=SimpleNamespace(cards=[{'function':'Nota MIDI','channel':1},card()],rule_config=RulesConfig())
        self.assertEqual(default_config(app,0).channel,3)



class Value:
    def __init__(self,value):self.value=value
    def get(self):return self.value
    def set(self,value):self.value=value


class NativeApplyTests(unittest.TestCase):
    def app(self):
        app=SimpleNamespace(cards=[{'function':'Nota MIDI','channel':1,'note':60,'cc':7,'visual':0,'axis':'Horitzontal'} for _ in range(16)],
            rule_config=RulesConfig(),audio_control_vars={},drum_notes={},rhythm_steps=[],mute_sent={},mute_retry_after={},
            active={},muted=False,bpm=120,deactivate=Mock(),select_card_preview=Mock(),sync_mute_controls=Mock(),
            update_cards_table=Mock(),send_rule_midi=Mock(return_value=True),kaoss_draft=KaossConfig())
        values={'card_id':'01','audio_duration':0,'mute_audible':0,'mute_silent':127,'fun':CHAOS_FUNCTION,
            'channel':2,'card_name':'Chaos de prova','drum_preset':'Rock bàsic','arp_direction':'Ascendent',
            'arp_division':'1/2 temps','arp_gate':60,'harmony_root':'La','harmony_scale':'Menor natural (eòlica)',
            'harmony_velocity':85,'axis':'Horitzontal','note':60,'cc':74,'visual':'visual','status':''}
        for name,value in values.items():setattr(app,name,Value(value))
        app.live_kaoss=LiveKaoss(app)
        return app

    def test_native_apply_saves_kaoss_into_project_card_and_configures_live_engine(self):
        app=self.app();self.assertTrue(method('apply_card')(app))
        self.assertEqual(app.cards[0]['function'],CHAOS_FUNCTION)
        self.assertEqual(KaossConfig.from_dict(app.cards[0]['kaoss']),app.kaoss_draft)
        saved=json.loads(json.dumps({'cards':app.cards}))
        self.assertEqual(live_configs(saved['cards'],RulesConfig()),app.live_kaoss.engine.configs)

    def test_native_apply_rejects_channel_conflict_before_mutating_card(self):
        app=self.app();app.channel.set(1);original=dict(app.cards[0])
        self.assertFalse(method('apply_card')(app))
        self.assertEqual(app.cards[0],original);self.assertFalse(app.live_kaoss.engine.configs)

    def test_native_apply_switching_function_releases_chaos_and_removes_live_config(self):
        app=self.app();apply=method('apply_card');self.assertTrue(apply(app))
        app.live_kaoss.observe(0,.5,.5,0);app.live_kaoss.tick()
        app.fun.set('Nota MIDI');self.assertTrue(apply(app))
        self.assertFalse(app.live_kaoss.engine.configs);self.assertFalse(app.live_kaoss.engine.voices)
        self.assertTrue(any(call.args[0].kind=='note_off' for call in app.send_rule_midi.call_args_list))

    def test_reserved_rule_channel_is_rejected(self):
        rules=SimpleNamespace(rules=[SimpleNamespace(enabled=True,actions=[SimpleNamespace(kind='note',channel=2)])])
        with self.assertRaises(ValueError):live_configs([card()],rules)


class IntegrationTests(unittest.TestCase):
    def test_function_dispatch_routes_every_existing_function(self):
        dispatch=method('open_function_settings')
        for function,target in ((CHAOS_FUNCTION,'open_kaoss_settings'),('Patró rítmic','open_music_settings'),
            ('Arpegiador espacial','open_music_settings'),('Ritme de bateria','open_music_settings'),
            ('Harmonia espacial','open_music_settings'),('Àudio','open_audio_settings'),
            ('Control MIDI CC','open_cc_settings'),('Control d’àudio / Mute','open_mute_settings'),
            ('Activar zona espacial','open_zone_editor'),('Nota MIDI','open_basic_function_settings'),
            ('Tempo','open_basic_function_settings'),('Canviar visual','open_basic_function_settings'),
            ('Cap acció','open_basic_function_settings')):
            app=Mock();app.fun.get.return_value=function;app.card_id.get.return_value='01'
            dispatch(app);getattr(app,target).assert_called_once()

    def test_automatic_table_selection_does_not_open_visuals(self):
        app=Mock();app.assigned_cards.selection.return_value=['0']
        app.preview_card=None;app.card_id.get.return_value='01'
        method('choose_assigned_card')(app)
        app.show_panel.assert_not_called();app.load_card.assert_called_once()

    def test_native_activate_routes_to_xy_and_does_not_send_native_note(self):
        app=Mock();app.muted=False;app.cards=[card()];app.active={}
        method('activate')(app,0,.4,.6,.2)
        app.live_kaoss.observe.assert_called_once_with(0,.4,.6,.2)
        app.midi.send.assert_not_called()

    def test_kaoss_specific_loss_timeout_controls_deactivation(self):
        app=Mock();app.cards=[card(KaossConfig(lost_timeout_s=1))];app.active={0:(.5,.5,0)};app.last_seen={0:1}
        expire=method('expire_missing_cards');expire(app,set(),1.5)
        app.deactivate.assert_not_called();expire(app,set(),2.1)
        app.deactivate.assert_called_once_with(0)

    def test_editor_rejects_draft_from_previous_project(self):
        editor=CardKaossEditor.__new__(CardKaossEditor)
        editor.generation=0;editor.app=SimpleNamespace(live_kaoss=SimpleNamespace(generation=1),apply_card=Mock())
        editor.error=Mock()
        self.assertFalse(editor.apply());editor.app.apply_card.assert_not_called()

    def test_editor_rejects_apply_to_different_card(self):
        editor=CardKaossEditor.__new__(CardKaossEditor)
        editor.generation=0;editor.index=0;editor.error=Mock()
        editor.app=Mock();editor.app.live_kaoss.generation=0;editor.app.card_id.get.return_value='02'
        self.assertFalse(editor.apply());editor.app.apply_card.assert_not_called()


if __name__=='__main__':unittest.main()
