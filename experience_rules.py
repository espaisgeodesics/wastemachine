"""Versioned declarative rules. No GUI, MIDI port, evaluation of code or outputs."""
from dataclasses import asdict, dataclass, replace
from math import isfinite
import re

TRIGGERS = ('zone_entered', 'zone_exited', 'marker_appeared', 'marker_absent', 'manual')
ACTION_KINDS = ('color', 'image', 'note', 'cc', 'release_visual')
MIDI_FUNCTIONS = {'Nota MIDI', 'Harmonia espacial', 'Arpegiador espacial', 'Control MIDI CC',
                  'Patró rítmic', 'Ritme de bateria', 'Àudio', 'Control d’àudio / Mute'}


def text(value, label, optional=False):
    if not isinstance(value, str) or len(value) > 256 or (not optional and not value.strip()) or any(ord(c) < 32 for c in value):
        raise ValueError(f'{label}: text no vàlid')
    return value


def integer(value, label, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f'{label}: enter entre {low} i {high}')
    return value


@dataclass(frozen=True)
class RuleAction:
    kind: str = 'color'
    value: str = '#FFFFFF'
    channel: int = 16
    number: int = 60
    velocity: int = 90
    duration_s: float = .25

    def __post_init__(self):
        if self.kind not in ACTION_KINDS:
            raise ValueError('Acció de regla no compatible')
        text(self.value, 'Valor', optional=True)
        integer(self.channel, 'Canal MIDI', 1, 16)
        integer(self.number, 'Nota / CC', 0, 127)
        integer(self.velocity, 'Velocitat', 1, 127)
        if isinstance(self.duration_s, bool) or not isinstance(self.duration_s, (int, float)) or not isfinite(self.duration_s) or not 0 <= self.duration_s <= 86400:
            raise ValueError('Durada no vàlida')
        if self.kind == 'note' and not .05 <= self.duration_s <= 60:
            raise ValueError('La nota ha de durar entre 0,05 i 60 segons')
        if self.kind == 'color' and not re.fullmatch(r'#[0-9A-Fa-f]{6}', self.value):
            raise ValueError('Color amb format #RRGGBB')
        if self.kind == 'image' and (not self.value.strip() or len(self.value) > 256 or not self.value.lower().endswith(('.jpg', '.jpeg', '.png'))):
            raise ValueError('Tria una imatge JPG o PNG')
        if self.kind == 'cc' and (not self.value.isascii() or not self.value.isdecimal() or not 0 <= int(self.value) <= 127):
            raise ValueError('El valor CC ha de ser un enter entre 0 i 127')


@dataclass(frozen=True)
class ExperienceRule:
    rule_id: str
    name: str
    trigger: str
    actions: tuple[RuleAction, ...]
    priority: int = 10
    group: str = 'escena'
    source_id: str = ''
    marker_id: int | None = None
    participant_id: str = ''
    zone_id: str = ''
    reason: str = 'movement'
    enabled: bool = True

    def __post_init__(self):
        for field in ('rule_id', 'name', 'group'):
            text(getattr(self, field), field)
        for field in ('source_id', 'participant_id', 'zone_id'):
            text(getattr(self, field), field, optional=True)
        if self.trigger not in TRIGGERS or self.reason not in ('movement', 'missing', 'any') or type(self.enabled) is not bool:
            raise ValueError('Activador, motiu o estat de regla no vàlid')
        if self.marker_id is not None:
            integer(self.marker_id, 'ID ArUco', 0, 15)
        integer(self.priority, 'Prioritat', 1, 1000)
        actions = tuple(self.actions)
        if not 1 <= len(actions) <= 8 or any(not isinstance(a, RuleAction) for a in actions):
            raise ValueError('Cada regla necessita entre una i vuit accions')
        object.__setattr__(self, 'actions', actions)

    def matches(self, event):
        return (self.enabled and event.kind == self.trigger
                and (not self.source_id or self.source_id == event.source_id)
                and (self.marker_id is None or self.marker_id == event.marker_id)
                and (not self.participant_id or self.participant_id == event.participant_id)
                and (not self.zone_id or self.zone_id == event.zone_id)
                and (self.trigger != 'zone_exited' or self.reason == 'any' or self.reason == event.reason))


@dataclass(frozen=True)
class RulesConfig:
    rules: tuple[ExperienceRule, ...] = ()

    def __post_init__(self):
        rules = tuple(self.rules)
        if len(rules) > 128 or any(not isinstance(r, ExperienceRule) for r in rules) or len({r.rule_id for r in rules}) != len(rules):
            raise ValueError('Regles duplicades o registre no vàlid (màxim 128)')
        object.__setattr__(self, 'rules', rules)

    def to_dict(self):
        return {'schema_version': 1, 'rules': [dict(asdict(rule), actions=[asdict(a) for a in rule.actions]) for rule in self.rules]}

    @classmethod
    def from_project(cls, data):
        if 'experience_rules' not in data:
            return cls()
        block = data['experience_rules']
        if not isinstance(block, dict) or type(block.get('schema_version')) is not int or block['schema_version'] != 1 or not isinstance(block.get('rules'), list):
            raise ValueError('Format de regles no compatible')
        if len(block['rules']) > 128:
            raise ValueError('Massa regles')
        try:
            rules = []
            for row in block['rules']:
                if not isinstance(row, dict) or not isinstance(row.get('actions'), list) or not 1 <= len(row['actions']) <= 8:
                    raise ValueError('Accions de regla no vàlides')
                rules.append(ExperienceRule(**dict(row, actions=tuple(RuleAction(**a) for a in row['actions']))))
            return cls(tuple(rules))
        except (TypeError, KeyError) as exc:
            raise ValueError('Configuració de regles no vàlida') from exc

    def validate_channels(self, cards):
        legacy = {int(c.get('channel', 1)) for c in cards if c.get('function') in MIDI_FUNCTIONS}
        legacy.update(int(c['mixer'].get('channel',c.get('channel',1))) for c in cards
                      if c.get('function') in MIDI_FUNCTIONS and isinstance(c.get('mixer'),dict))
        reserved = {a.channel for r in self.rules if r.enabled for a in r.actions if a.kind in ('note', 'cc')}
        conflict = legacy & reserved
        if conflict:
            raise ValueError('Els canals MIDI de les regles han de ser diferents dels de les targetes: ' + ', '.join(map(str, sorted(conflict))))


@dataclass(frozen=True)
class ActionRequest:
    rule: ExperienceRule
    action: RuleAction
    event: object
    action_index: int


class RuleEngine:
    def __init__(self, config=None):
        if config is not None and not isinstance(config, RulesConfig):raise ValueError('Configuració de regles no vàlida')
        self.config = config if config is not None else RulesConfig()
        self.last_sequence = 0

    def consume(self, events, registry=None):
        requests = []
        retired = {pid for pid, state in registry.states({}).items() if state.presence == 'retired'} if registry else set()
        for event in sorted(events, key=lambda e: e.sequence):
            if event.sequence <= self.last_sequence:
                continue
            self.last_sequence = event.sequence
            if event.participant_id in retired:
                continue
            for rule in sorted(self.config.rules, key=lambda r: (-r.priority, r.rule_id)):
                if rule.matches(event):
                    requests.extend(ActionRequest(rule, action, event, i) for i, action in enumerate(rule.actions))
        return tuple(requests)

    def manual(self, rule_id, now):
        from domain_events import DomainEvent
        if isinstance(now,bool) or not isinstance(now,(int,float)) or not isfinite(now) or now<0:raise ValueError('Temps manual no vàlid')
        rule = next((r for r in self.config.rules if r.rule_id == rule_id),None)
        if rule is None:raise ValueError('Regla desconeguda')
        if not rule.enabled:
            return ()
        event = DomainEvent(0, now, 'manual', rule.source_id or 'operator', marker_id=rule.marker_id,
                            participant_id=rule.participant_id or None, zone_id=rule.zone_id or None)
        return tuple(ActionRequest(rule, action, event, i) for i, action in enumerate(rule.actions))


def rebase_rule_images(config, old_project, new_project):
    from pathlib import Path
    from spatial_zones import image_reference
    def rebase(action):
        if action.kind != 'image':
            return action
        path = Path(action.value)
        if not path.is_absolute():
            if old_project is None:
                raise ValueError('Cal resoldre la imatge de la regla abans de desar')
            path = Path(old_project).resolve().parent / path
        return replace(action, value=image_reference(path, new_project))
    return RulesConfig(tuple(replace(rule, actions=tuple(rebase(a) for a in rule.actions)) for rule in config.rules))
