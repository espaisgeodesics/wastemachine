# ATMO ESFERA FX · Integració 15

Obre la carpeta completa amb **OBRIR_ATMO.bat** o **OBRIR_ATMO_15.bat**.
Els llançadors es mantenen a Python 3.12. La branca de treball és exclusivament
`atmo/interficie-primera-integracio`.

## Zones amb imatge i so

Una zona pot tenir imatge, so o tots dos. A l'editor de zones hi ha:

- Fitxer WAV PCM / OGG, volum 0–1, fade in i fade out de 0–10 segons.
- Repetició en bucle i tres modes: mentre hi hagi una targeta autoritzada,
  reproduir un cop, o continuar uns segons després de sortir.
- Permetre solapament de zones i prioritat d'imatge (nombre més alt guanya).
- Un botó per activar el dispositiu d'àudio local i la marca ♪ a les caselles
  amb so. Les propietats són al panell lateral desplaçable.

El so utilitza el motor local existent: clips de fins a **30 segons**, repetibles
en bucle, i fins a **16 veus locals** compartides amb l'àudio de regles. No és
reproducció de cançons llargues ni MP3, i no envia aquests fitxers per MIDI.
Si falten les dependències, executa **INSTAL_LAR_AUDIO_LOCAL.bat** i torna a
activar l'àudio. La instal·lació també està fixada al Python 3.12 del llançador.

**Mentre hi hagi una targeta:** fade in en entrar i fade out quan surt l'última.
**Segons després de sortir:** espera el temps indicat i després inicia el fade out.
**Reproduir un cop:** ignora el bucle i deixa acabar el clip; no aplica el fade out
per sortida. Les aturades de seguretat, el canvi de projecte i el silenci poden
aturar-lo immediatament.

Dues targetes dins d'una mateixa zona comparteixen una sola reproducció: no es
reinicia ni es duplica a cada detecció. Les zones sonores diferents tenen capes
independents i poden sonar simultàniament, fins i tot si coincideixen amb una zona
d'imatge. Una zona que conté imatge i so activa totes dues sortides amb la mateixa
presència estabilitzada i les mateixes autoritzacions.

Triar un fitxer de so activa **Permetre solapament**. Per crear una capa damunt
una zona existent, tria primer el so o activa aquesta casella, i després selecciona
les caselles del mapa. El comportament antic sense solapaments continua sent el
predeterminat per a zones noves sense so. Les parelles de zones només poden
solapar-se si almenys una ho permet explícitament.

Quan coincideixen imatges, es mostra una sola imatge: primer la prioritat més alta,
i en empat l'identificador de zona en ordre estable. Una capa només sonora no
amaga una fotografia. Es respecten les autoritzacions de cada targeta. Les regles
espacials continuen rebent la zona prioritària; les capes de so tenen detectors
independents i no afegeixen esdeveniments duplicats al registre de regles.

Cal calibrar el mapa per activar les zones amb la càmera i assignar a les targetes
la funció **Activar zona espacial**, igual que per a les imatges existents.
Els errors del dispositiu o de lectura de so es mostren a l'estat i al registre
d'àudio local. Un so que falla no impedeix mostrar la imatge de la zona.

## Desament i compatibilitat

S'emmagatzemen les propietats noves dins de cada zona. La versió espacial del
format passa a 2; es continuen llegint els projectes espacials de versió 1.
Les versions anteriors d'ATMO no poden llegir el format espacial nou: a la primera
prova utilitza **Desar com...** amb un nom nou per conservar l'original.
Les rutes d'imatge i so s'ajusten juntes en desar i en canviar de carpeta amb
Desar com..., mantenint la identitat dels recursos. Els fitxers de so no s'incrusten
al JSON: cal conservar-los amb el projecte o a les seves rutes originals.

## Menús i aparença

- **Participants** i **Regles** només apareixen al menú superior en mode **Joc**.
  No apareixen en Música, Exposició ni Instal·lació immersiva.
- Les barres de títol utilitzen el mode fosc natiu de Windows i conserven els
  controls de moure, redimensionar, minimitzar i tancar. Windows 10 admet el mode
  fosc; el blau ATMO exacte per a la barra i les vores només s'aplica si Windows
  admet aquests atributs. No es crea cap capçalera sense vores ni finestres modals.
- S'elimina el marc de coure i els reblons de l'editor de targetes i dels panells
  antics. Les vores de l'àrea principal i de l'estat són de la paleta ATMO.
- Es mantenen les correccions d'arrencada, ordre de finestres i Chaos de la 14.

## Validació

176 proves executades: **172 superades i 4 omeses** per dependències opcionals o
comprovacions de dispositiu no disponibles. S'inclouen reproducció i barreja amb
el backend silenciós real, fades, ocupació compartida, presència autoritzada,
calibratge, absència, reentrada, imatge simultània, prioritat, errors de fitxer,
àudio desactivat, desament i canvi de carpeta, esquemes antic/nou, formulari de
zona, menús per modalitat, atributs natius de títol simulats i regressions de Chaos,
projecció, seguiment i interfície. Sintaxi revisada a tots els fitxers Python.

Falta la validació visual i de so físic a Windows. Prova curta:

1. Entrar en Música: el menú no ha de tenir Participants ni Regles. Comprovar les
   barres de títol i que l'editor de targetes no tingui el requadre marró.
2. En una còpia del projecte, crear una zona amb imatge i so WAV/OGG curt, autoritzar
   una targeta, aplicar, calibrar i activar àudio local.
3. Entrar amb la targeta: imatge i so alhora. Sortir: comprovar el fade out.
4. Crear una altra zona només sonora solapada: han de sonar dues capes sense que
   desaparegui la imatge. Provar dues targetes en una zona: només una reproducció.
5. Provar els tres modes i el silenci absolut; desar amb un nom nou, tancar i
   reobrir per revisar els fitxers, les rutes i tots els paràmetres.
