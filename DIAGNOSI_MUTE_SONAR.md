# Diagnosi mínima del Mute a Sonar — Wasteland 4.6.2

## Resultat de la revisió

La revisió parteix de la versió actual 4.6.1 i conserva les funcions i els formats de projecte existents. No pressuposa que la còpia antiga 4.5.15 sigui idèntica a la que s'està executant a Windows; comprova la versió i el fitxer a Ajuda.

La funció Nota MIDI envia un `note_on` amb velocitat 100 la primera vegada que la targeta entra a l'estat actiu. Els fotogrames següents no repeteixen l'ordre. El bucle de càmera actualitza `last_seen`; passats més de 250 ms sense tornar a veure el marcador, crida `deactivate`, que envia un `note_off` amb velocitat 0, al mateix canal i nota registrats. Elimina l'estat actiu, de manera que una aparició posterior torna a enviar un `note_on`.

S'ha comprovat automàticament aquest cicle amb imatges ArUco sintètiques processades pel detector real i amb una sortida MIDI de prova: `note_on → note_off → note_on → note_off`. També s'ha verificat que una absència més curta que el llindar no retiri la targeta. Això comprova la lògica local, no la càmera física, loopMIDI ni Sonar.

Hi havia un punt cec: diverses rutes, inclosa la retirada de notes, capturen errors d'enviament sense mostrar-los. La diagnosi nova registra també els errors abans que aquests gestors els capturin. Aquesta revisió no modifica el protocol Nota MIDI ni canvia la temporització de retirada per intentar corregir un comportament de Sonar encara desconegut.

**No s'ha establert la causa exacta del problema a l'ordinador de Jordi.** La primera desactivació de Mute només prova una acció del receptor. No demostra que el Note Off següent hi arribi, ni que Remote Control → Note On/Off el converteixi en l'estat contrari del Mute.

## Què aporta la modificació

Al panell MIDI hi ha el botó **DIAGNOSI MIDI**. El registre inclou:

- Hora amb mil·lisegons, aparició i retirada de targetes.
- Tipus de missatge, canal expressat com 1–16, nota i velocitat, o CC i valor (nombres decimals).
- `ACCEPTAT PEL PORT LOCAL` si l'API del port no ha retornat error, o `ERROR LOCAL` si ha fallat.
- Còpia al porta-retalls i exportació a text, amb un màxim de 1.000 línies en memòria. No s'escriu cap fitxer automàticament.

**Acceptació local no vol dir recepció a Sonar ni confirmació de l'estat del Mute.** Si cal comprovar la recepció independentment de Remote Control, utilitza un monitor MIDI al port de destinació i compara els missatges; el registre de Wasteland no el substitueix.

## Prova 1 — Nota actual

1. Connecta la sortida `wasteland MIDI 1` i obre DIAGNOSI MIDI. Utilitza només una targeta de prova. Evita que una altra pista d'instrument tingui aquest port i canal com a entrada si no vols disparar sons durant la prova.
2. Neteja el registre. Mostra la targeta, retira-la durant un segon, torna-la a mostrar i retira-la de nou.
3. El registre ha de contenir dues línies VISIBLE i dues RETIRADA, i els quatre missatges `note_on`, `note_off`, `note_on`, `note_off`, amb el mateix canal i nota.
4. Si no apareix RETIRADA, comprova la detecció al monitor de targetes. Si apareix un ERROR LOCAL en el Note Off, tenim una fallada d'enviament a investigar. Si hi ha acceptació local de tots quatre, cal comprovar el receptor i l'assignació de Sonar; no concloure que han arribat només pel registre.

## Prova 2 — Valors de CC sense disparar notes

La finestra de diagnosi ofereix dues ordres de prova **ENVIAR 0** i **ENVIAR 127**, amb canal i CC configurables. No s'executen automàticament. Per defecte suggereix canal 1 i CC119; comprova que aquest CC estigui lliure en el projecte o tria'n un altre.

1. Tanca la càmera per evitar que altres targetes enviïn notes durant aquesta prova. Mantén Sonar reproduint el projecte en bucle; no canviïs el Play general.
2. A Remote Control del Mute de la pista d'àudio de prova, substitueix temporalment l'associació de nota per una de Controller/CC, amb el canal i CC de la diagnosi. Si fas Learn, prem ENVIAR 127 per presentar el missatge; comprova que Sonar hagi après un CC i no una nota. Conserva les dades de l'assignació antiga si la vols recuperar.
3. Prem, amb un segon entre pulsacions: **0, 0, 127, 127**. Anota el Mute observat després de cada ordre:

| Ordre | Mute a Sonar: activat o desactivat? |
|---|---|
| CC valor 0 | Per verificar |
| CC valor 0 repetit | Per verificar |
| CC valor 127 | Per verificar |
| CC valor 127 repetit | Per verificar |

4. Per considerar el control absolut verificat, el mateix valor ha de mantenir el mateix estat encara que es repeteixi, i els dos valors han de produir estats oposats. No pressuposem si 0 significa silenci o audible: ho determinarà aquesta prova.
5. Si cada ordre alterna el botó, o només un valor fa efecte, aquesta modalitat de Remote Control no és una assignació absoluta fiable. Cal trobar una assignació/paràmetre de dos estats adequada a Sonar abans d'automatitzar-ne la presència.

## Estratègia proposada després de la prova

La funció Control MIDI CC existent és contínua: envia valors de moviment mentre la targeta és visible, però **no envia un valor d'absència quan es retira**. Tampoc la funció Àudio (dispar one-shot) és un control de Mute per presència.

Si es verifica l'assignació absoluta, la modificació següent serà una funció dedicada **Control d'àudio / Mute**, amb canal, CC, valor audible i valor silenciat configurables. En entrar enviarà el valor audible; en sortir, després del llindar ArUco, el silenciat. Caldrà definir i provar també l'estat absent en connectar MIDI, aplicar la configuració, perdre la càmera i tancar el programa. No enviarà notes ni ordres de transport de Sonar.

Aquest disseny de dos estats és preferible a alternar el Mute amb pulsos: repetir una ordre explícita no hauria de desincronitzar el botó. Però només és vàlid si el receptor admet aquests estats absoluts. La funció nova no s'ha implementat encara per evitar donar per certa aquesta compatibilitat sense prova.

## Validació

Les 35 proves han passat, incloses el detector ArUco amb fotogrames sintètics, l'alliberament i reaparició, el registre d'un error deliberat de Note Off, la traça del port, l'exportació del registre i la prova CC sense notes. Les comprovacions amb Windows 10, la càmera, loopMIDI i el Mute del Sonar real queden pendents. Per continuar, cal el registre de la prova 1 i els quatre estats observats a la prova 2.
