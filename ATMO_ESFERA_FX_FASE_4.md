# ATMO ESFERA FX — fase 4: regles i propietat de sortides

Entrega: **Wasteland Machine 4.7.9**, sobre la [fase 3, 4.7.8](ATMO_ESFERA_FX_FASE_3.md),
commit recuperable `6010af0`, a `codex/wasteland-camera-windows-launcher`.

## Crear i executar una regla

Obre **Regles → Regles i sortides…**. El formulari permet:

1. Posar nom i triar **Entrada de zona, Sortida de zona, Aparició, Absència
   confirmada o Ordre manual**.
2. Limitar font, ID ArUco, participant o zona. Buit significa qualsevol.
   Participants i zones es poden triar pel nom als desplegables; es conserva
   l’ID estable. També s’admet escriure un ID explícit.
3. Assignar prioritat (1–1000), grup visual i estat actiu/desactivat.
4. Afegir entre una i vuit accions a la llista: **Color, Imatge, Nota MIDI,
   MIDI CC o Alliberar grup visual**. Selecciona una acció i prem **CANVIAR ACCIÓ**
   per editar-la; això conserva les altres. Només s’habiliten els paràmetres
   pertinents al tipus d’acció.
5. Prémer **APLICAR REGLA** i desar el projecte. Aplicar reinicia les sortides
   de les regles anteriors, sense enviar les accions noves automàticament.

Una regla aplicada espera un esdeveniment nou; no inventa una aparició o entrada
perquè el marcador ja sigui present. **EXECUTAR** és una ordre explícita de
l’operador: executa totes les accions de la regla seleccionada i activa,
independentment de les condicions. Al formulari real pot enviar MIDI i canviar
la projecció. Una regla desactivada no s’executa ni manualment.

Els canvis pendents de formulari o d’acció es comproven abans de desar,
canviar de regla, tancar o obrir un projecte. Els formularis de regles tenen
barra de desplaçament per a pantalles petites. **ALLIBERAR SORTIDA** elimina
els propietaris visuals de regles i torna a mostrar la sortida de compatibilitat
actual, que pot ser una fotografia persistent o els visuals existents.

## Accions, prioritats i durades

**Color** utilitza `#RRGGBB` i produeix un fotograma uniforme. **Imatge** accepta
JPG/PNG, conserva proporcions i transparència sobre negre mitjançant el carregador
existent. Una imatge absent o corrupta es registra al diagnòstic i no substitueix
una ordre visual ja acceptada dins de la mateixa sessió.

Per color/imatge, **durada 0 = persistent** fins a alliberar el grup o la sortida;
una durada positiva fa caducar la propietat. La prioritat més alta guanya.
Amb la mateixa prioritat guanya la confirmació més recent; en empat temporal,
ID estable de regla, font, ID de marcador i ordre d’acció resolen el resultat.
En un fotograma simultani l’ID de marcador més baix desempata dins la mateixa
regla. No depèn de l’ordre retornat pel detector.

Cada propietat conserva grup, regla, font, marcador i acció. Una ordre de color
no torna a reclamar la sortida a cada fotograma immòbil. Quan caduca un
propietari, pot reaparèixer un propietari vigent de prioritat inferior. Quan
no en queda cap, es recupera la sortida existent. El lot d’accions es processa
abans de dibuixar: no es projecta un negre intermedi entre alliberar i reclamar.

**Alliberar grup visual** utilitza el grup de la regla. Amb un esdeveniment de
marcador allibera només aquell grup per la mateixa font i marcador; una ordre
manual sense ID pot alliberar el grup sencer. Això permet una regla d’entrada
i una altra de sortida amb el mateix grup sense apagar les altres persones.

Els modes persistent/presència/retard de les fotografies de zones anteriors
continuen pel camí de compatibilitat. No es migren automàticament a regles.
Les imatges noves de regla tenen la seva pròpia durada i/o regla d’alliberament.

**MIDI CC** envia un valor 0–127. Les ordres contradictòries al mateix canal/CC
del mateix lot es resolen per prioritat i desempat estable; només s’envia la
guanyadora. És una ordre puntual: una ordre confirmada en un lot posterior pot
enviar un altre valor. No s’afirma conèixer l’estat final del receptor.

**Nota MIDI** utilitza canal, nota, velocitat i durada entre 0,05 i 60 segons.
Si diverses regles mantenen la mateixa nota/canal, s’envia un sol Note On i
el Note Off només quan acaba l’últim propietari. La primera pulsació determina
la velocitat; una nota ja mantinguda no es torna a disparar per afegir un
propietari. El final de les notes corre al fil musical, independentment de Tk
o la lectura de càmera. Els Note Off fallits es reintenten durant l’execució.

Els canals utilitzats per accions MIDI de regles han de ser diferents dels
configurats a les targetes musicals/CC/Mute i al mesclador. Es valida en aplicar
regles, carregar projecte i modificar targetes o rutes del mesclador. El canal
16 es proposa al formulari, però s’ha de triar un canal lliure de la configuració.
És la frontera de propietat amb el MIDI de compatibilitat: no es reescriuen
els seus generadors ni es filtren els seus missatges.

El silenci absolut bloqueja nous MIDI de regles. Desconnectar, canviar de
projecte/configuració, tancar càmera o sortir intenta acabar les notes de regles
i alliberar sustain als canals utilitzats. Sense port, o amb enviament fallit,
es deixa diagnòstic; no es difereix un Note On per disparar-lo en reconnectar.
L’acceptació local no confirma recepció a Sonar ni atura el seu transport.

## Esdeveniments dubtosos i compatibilitat

Els marcadors d’un participant retirat no executen regles automàtiques. Les
avaries de font no són activadors d’aquest primer motor. Per defecte, una regla
de sortida de zona exigeix `movement` (**moviment**); no tracta una pèrdua o
revalidació com a moviment físic.

El selector de motiu permet `missing` (sortida confirmada per imatges vàlides
sense el marcador) o `any` (qualsevol motiu, inclosa `detection_gap`). El motiu
només filtra sortides de zona. Per a pèrdua prolongada es pot utilitzar el
disparador específic **Absència confirmada**. No s’han implementat penalitzacions,
vides ni estats de joc.

Amb zero regles, la projecció i el MIDI mantenen el comportament de 4.7.8.
Els generadors existents continuen actius. Les accions noves del flux de càmera
es posen en cua i s’apliquen després del pas de compatibilitat, una sola vegada.
Les regles visuals reclamen prioritat superior a la sortida antiga només quan
accepten una acció; els fotogrames posteriors no dupliquen el disparador.

## Proves al simulador

**CARREGAR ZONES I REGLES DEL PROJECTE** copia la configuració al simulador.
Les fonts de càmera explícites es tradueixen a `simulator:0`; els filtres de
participant es vinculen a la persona virtual amb el mateix marcador. Si no hi
ha correspondència, es rebutja la còpia amb diagnòstic. Aquesta font virtual
única no valida interaccions entre múltiples càmeres reals.

**REGLES DE PROVA...** obre el mateix formulari sobre la sessió virtual. Aquí
APLICAR i EXECUTAR només afecten sortides de prova. La pestanya **Sortida de
prova** mostra imatge/color, propietari visual i els missatges MIDI simulats
(tipus, canal, nota/CC i valor). No obre cap port MIDI ni modifica la projecció,
el projecte o els participants reals.

El simulador utilitza els mateixos models i àrbitres. Les notes són registres
simulats, no so; el seu rellotge avança amb la sessió de prova. Tancar la finestra
finalitza les notes de prova i conserva configuració/posicions en memòria.
**REINICIAR PROVA** conserva la còpia del mapa i de les regles, i buida estat
transitori. Les modificacions virtuals no es desen al projecte real.

## Format, recursos i límits

Mòduls nous: `experience_rules.py` (dades i selecció), `rule_outputs.py`
(propietat visual i notes) i `rule_editor.py` (formulari). No hi ha dependències
noves. El BAT general comprova que tots els fitxers siguin presents.

El projecte conserva versió arrel 4 i incorpora `experience_rules` amb
`schema_version: 1`. Exemple mínim vàlid:

```json
{
  "experience_rules": {
    "schema_version": 1,
    "rules": [{
      "rule_id": "bosc-blau",
      "name": "Bosc blau",
      "trigger": "zone_entered",
      "zone_id": "id-estable-de-la-zona",
      "priority": 10,
      "group": "bosc",
      "actions": [
        {"kind": "color", "value": "#2468AC", "duration_s": 0},
        {"kind": "note", "channel": 16, "number": 60, "velocity": 90, "duration_s": 0.2},
        {"kind": "cc", "channel": 16, "number": 74, "value": "99"}
      ]
    }]
  }
}
```

Les regles es validen abans de modificar el projecte o enviar MIDI. No s’executa
codi de configuració. Els projectes antics sense el bloc obren amb zero regles.
`Desar com` conserva la identitat de les imatges amb rutes rebasades. El desament
del JSON ara escriu un temporal al mateix directori i substitueix el destí
només després d’una escriptura correcta: un error deixa l’original intacte.

No es desen propietaris actius, notes pendents, rellotges ni historials. Límits:
128 regles, 8 accions per regla, cua de 4096 accions, 256 propietaris visuals,
256 notes pendents, 4 imatges diferents amb propietari actiu i registres de
200 entrades. El límit d’imatges evita retenir una imatge gran per cadascuna
de centenars de regles. Les accions rebutjades es diagnostiquen i no desplacen
la sortida vàlida. Un error d’acció no desfà altres accions ja acceptades del lot.

## Validació i recuperació

**206 proves correctes, cap omesa**, amb Python 3.12, pantalla virtual Xorg i
les versions exactes de `requirements.txt`. Les 171 proves de referència es van
executar abans d’afegir les proves de regles i continuen incloses a la suite.

Les proves cobreixen validació i configuració sense codi, deduplicació,
filtres/retirada, execució manual, prioritats i desempats, persistència,
alliberament, recursos absents, límits, CC contradictoris, notes compartides,
reintents, silenci, canals reservats, mesclador, final de notes sense actualitzar
Tk, projectes antics/nous, Desar com i error d’escriptura sense perdre l’original.

Una prova completa usa el detector OpenCV real sobre cinc marcadors sintètics:
conserva cinc notes MIDI antigues, activa una imatge per regla i envia només
una nota compartida i un CC de regles. Es mantenen les regressions de càmera,
MIDI, visuals, durades de fotografies, zones, calibració i projectes anteriors.
També s’ha executat el bucle real de Tkinter amb cinc participants virtuals,
editor, previsualització i MIDI simulat sense cap enviament real.

```text
python -m unittest discover -s tests -v
```

El punt de recuperació és `6010af0`, amb el projecte original. Una versió antiga
pot perdre el bloc nou si hi torna a desar el projecte: conserva una còpia i
utilitza Desar com. Windows, dispositius físics i Sonar segueixen pendents de
prova a la instal·lació. La fase següent és el backend d’àudio local i una
primera experiència BOSC VIU; aquesta entrega només envia MIDI, no reprodueix
sons locals ni incorpora encara Kaoss o joc.
