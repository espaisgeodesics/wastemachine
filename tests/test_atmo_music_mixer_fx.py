import unittest
from types import SimpleNamespace
from unittest.mock import Mock,patch
from atmo_music import arp_pitches, arpeggio_note, sequence_notes, music_zone, parse_notes
from atmo_mixer import midi_level,note_velocity,sound_kind,independent_channels
from atmo_ambience import ambience_preset,effect_channels,normalise_ambience_card,mapped_cc
from atmo_card_functions import LiveKaoss,CHAOS_FUNCTION
from experience_rules import RulesConfig
from atmo_windows import maximize_window

SCALES={'Major':[0,2,4,5,7,9,11]}

class MusicTests(unittest.TestCase):
    def test_five_notes_ascending_descending_and_bounce(self):
        card=dict(arp_note_count=5,arp_octaves=2)
        pitches=arp_pitches(card,0,1,[60,64,67],SCALES)
        self.assertEqual(pitches,[60,64,67,72,76])
        self.assertEqual([arpeggio_note(pitches,i,'Descendent') for i in range(5)],list(reversed(pitches)))
        self.assertEqual(sequence_notes(pitches,'Pujada i baixada'),[60,64,67,72,76,72,67,64])
    def test_legacy_auto_is_preserved(self):
        self.assertEqual([len(arp_pitches({},0,ring,[60,64,67],SCALES)) for ring in range(3)],[4,3,2])
    def test_custom_notes_preserve_order_and_register(self):
        card=dict(arp_note_count=3,arp_source='Notes triades',arp_notes=[67,60,64])
        self.assertEqual(arp_pitches(card,0,1,[],SCALES),[67,60,64])
        self.assertEqual(arp_pitches(card,0,2,[],SCALES),[55,48,52])
        with self.assertRaises(ValueError):parse_notes('60 x 64')
    def test_grid_cells_follow_position_and_boundaries(self):
        card=dict(function='Arpegiador espacial',arp_map='grid')
        self.assertEqual(music_zone(card,.99,.99),(7,2))
        self.assertEqual(music_zone(card,0,0),(0,0))
        self.assertEqual(music_zone(card,1,1),(7,2))
    def test_scale_and_unavailable_note_counts(self):
        card=dict(arp_note_count=7,arp_source='Escala',harmony_scale='Major',harmony_root=0)
        self.assertEqual(len(arp_pitches(card,0,1,[],SCALES)),7)
        with self.assertRaises(ValueError):arp_pitches(dict(arp_note_count=32),0,1,[60,64,67],SCALES)
    def test_maximize_and_fallback(self):
        window=Mock();maximize_window(window);window.state.assert_called_once_with('zoomed')
        window.state.side_effect=RuntimeError();window.winfo_screenwidth.return_value=1920;window.winfo_screenheight.return_value=1080
        maximize_window(window);window.geometry.assert_called_once_with('1920x1080+0+0')

class MixerTests(unittest.TestCase):
    def cards(self,shared=False):return [dict(function='Nota MIDI',channel=1,mixer=dict(level=64)),dict(function='Arpegiador espacial',channel=1 if shared else 2)]
    def test_master_and_card_gains_multiply_on_independent_channels(self):
        self.assertEqual(midi_level(self.cards(),0,64),32)
        self.assertEqual(midi_level(self.cards(),1,64),64)
        self.assertEqual(note_velocity(self.cards(),0,100),100)
    def test_shared_channels_preserve_master_and_scale_new_notes(self):
        cards=self.cards(True)
        self.assertEqual(midi_level(cards,0,64),64)
        self.assertEqual(note_velocity(cards,0,100),50)
        self.assertEqual(note_velocity(cards,1,100),100)
    def test_allocator_separates_tracks_without_mutating_original(self):
        cards=self.cards(True);result=independent_channels(cards,RulesConfig())
        self.assertEqual([c['channel'] for c in result],[1,2]);self.assertEqual(cards[1]['channel'],1)
        self.assertEqual(result[0]['mixer']['level'],64)
        self.assertTrue(all(c['mixer']['cc']==7 for c in result))
    def test_effects_and_visuals_have_no_volume(self):
        cards=[dict(function='Canviar visual'),dict(function=CHAOS_FUNCTION,kaoss=dict(mode='Efectes'))]
        self.assertEqual([sound_kind(cards,i) for i in range(2)],['none','none'])

class EffectTests(unittest.TestCase):
    def app(self,release='neutral'):
        config,metadata=ambience_preset('Cova',1)
        fx=dict(function=CHAOS_FUNCTION,channel=1,kaoss=config.to_dict(),**metadata);fx['kaoss_release']=release
        app=SimpleNamespace(cards=[fx,dict(function='Nota MIDI',channel=1),dict(function='Arpegiador espacial',channel=3)],muted=False,bpm=120,send_rule_midi=Mock(return_value=True))
        live=LiveKaoss(app);live.configure(app.cards,RulesConfig());return app,live
    def test_effects_share_instrument_channel_and_never_generate_notes(self):
        app,live=self.app();live.observe(0,.5,.5,0);live.tick()
        commands=[call.args[0] for call in app.send_rule_midi.call_args_list]
        self.assertTrue(commands);self.assertTrue(all(c.kind=='cc' for c in commands))
        self.assertEqual({c.channel for c in commands},{1,3})
        live.release(0);self.assertFalse(live.fx_values)
        self.assertTrue(all(c.args[0].kind=='cc' for c in app.send_rule_midi.call_args_list))
    def test_selected_targets_and_parameter_range(self):
        app,_=self.app();app.cards[0].update(kaoss_target='selected',kaoss_targets=[2])
        self.assertEqual(effect_channels(app.cards,0),{3})
        self.assertEqual(mapped_cc(app.cards[0],74,0)[0],25)
        self.assertEqual(mapped_cc(app.cards[0],74,127)[0],90)
    def test_hold_persists_until_panic(self):
        app,live=self.app('hold');live.observe(0,.5,.5,0);live.tick();app.send_rule_midi.reset_mock()
        live.release(0);self.assertTrue(live.fx_values);app.send_rule_midi.assert_not_called()
        self.assertTrue(live.stop());self.assertFalse(live.fx_values);self.assertTrue(app.send_rule_midi.called)
    def test_legacy_instrument_configuration_is_backed_up(self):
        original=dict(mode='Instrument',channel=2,root=9)
        card=dict(function=CHAOS_FUNCTION,channel=2,kaoss=original.copy());normalise_ambience_card(card)
        self.assertEqual(card['kaoss']['mode'],'Efectes');self.assertEqual(card['kaoss_instrument_legacy'],original)

if __name__=='__main__':unittest.main()
