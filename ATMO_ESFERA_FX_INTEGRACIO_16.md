# ATMO ESFERA FX · Integració 16

Obre la carpeta completa amb **OBRIR_ATMO.bat** o **OBRIR_ATMO_16.bat**.
Es manté Python 3.12, el so de zones, Chaos i les correccions de finestres.

## Visual assignat: Cap

El selector de visuals de targeta inclou **Cap** com a primera opció. Impedeix que
la targeta generi un visual propi però conserva la seva funció de so, notes MIDI,
CC, Chaos o altres accions. Les imatges configurades explícitament en zones o
regles continuen sent sortides independents: no s'esborren per aquesta opció.

Els índexs antics de visuals 0–12 es conserven; Cap es desa com a 13. Els projectes
anteriors mantenen els visuals que ja tenien assignats. Les targetes d'un projecte
nou comencen amb Cap: ja no s'assigna automàticament el cercle cromàtic a T01.
Quan no hi ha visuals, imatges de zona ni regles visuals actives, el projector
queda negre. Les imatges configurades expressament com a persistents conserven
el seu comportament.

## Previsualització com a mapa d'operador

A la finestra Visual, el selector **Mapa de previsualització** permet triar
**Cercle**, **Quadrat** o **Rectangle**. La tria es desa al projecte. Canvia la forma
de la vista d'operador; no modifica els límits circulars de les zones existents ni
la geometria de calibratge o la sortida del projector.

El mapa mostra les targetes actives, la posició i el gir, les trajectòries recents,
la funció i, si té un visual generatiu assignat, una miniatura que es mou amb la
targeta. Les targetes amb Cap també es veuen al mapa, identificades com a tals,
per poder seguir targetes que només activen so o MIDI.

Amb calibratge s'utilitzen les coordenades projectades al terra. Sense calibratge,
la vista ho indica i mostra coordenades normalitzades de càmera; no es presenta
com una mesura física. Els punts fora del mapa no es forcen artificialment a la
vora. La simulació amb el ratolí utilitza la mateixa geometria de mapa i, si cal,
la transformació inversa del calibratge.

Si una targeta activa té el visual **Cercle cromàtic 360°**, el color RGB calculat
s'aplica a la **franja exterior del mapa**, deixant l'interior per a la resta de
visuals, imatges i targetes. El visual cromàtic del projector continua disponible:
quan coincideix amb altres visuals generatius es barregen, sense que el color pla
els amagui. Si hi ha diverses targetes cromàtiques, es tria l'ID més baix de manera
estable. Les zones d'imatge i les regles conserven la seva prioritat existent.

## Projector separat

El mapa, el contorn, les miniatures, les trajectòries, els números de targeta, els
textos i les guies **només es generen a la previsualització**. La projecció i la
gravació continuen utilitzant el fotograma net de sortida. La vista d'operador
construeix una còpia: no pinta damunt de les imatges ni dels visuals originals.

## LED i DMX: fase posterior

És possible enviar el mateix RGB cromàtic a un focus LED per USB–DMX. No s'envia
cap senyal DMX en aquesta versió ni s'afegeixen dependències de maquinari. Quan
l'usuari triï l'equip caldrà identificar el protocol de la interfície USB, el mode
del focus (RGB/RGBW/dimmer), l'adreça inicial i l'ordre dels canals. No es pot
suposar que qualsevol adaptador USB–DMX utilitzi el mateix protocol.

## Validació

192 proves executades: **188 superades i 4 omeses** per comprovacions opcionals
no disponibles. Les 16 proves noves cobreixen compatibilitat d'índexs, Cap sense
interferir amb MIDI/so, negre en repòs, figures i color sense marques al projector,
protecció d'imatges originals, franja cromàtica exterior, formes, coordenades
calibrades i correspondència entre ratolí i mapa. Es mantenen les proves de zones,
so, fades, finestres, menús, desament i Chaos. Sintaxi revisada a tot el Python.
També s'ha inspeccionat una imatge de prova del renderitzador del mapa; no és una
prova de càmera, MIDI ni GUI real a Windows.

Prova curta a Windows:

1. Projecte nou → connectar càmera i MIDI si cal → obrir Visual: mapa sense demo
   cromàtica i projector negre mentre no hi hagi cap sortida visual activa.
2. Assignar Cap a una targeta de so o MIDI: l'acció ha de continuar funcionant,
   amb una marca al mapa però sense visual propi al projector.
3. Assignar Cercle cromàtic 360° a una altra targeta: el color ha de quedar a fora
   del mapa d'operador. Assignar un altre visual a una tercera targeta i comprovar
   la figura, la posició i el moviment.
4. Obrir Projecció: no hi ha d'haver números, fletxes, mapes ni textos d'operador.
5. Canviar Cercle/Quadrat/Rectangle, provar la simulació amb ratolí i desar amb un
   nom nou. Reobrir per revisar la forma del mapa i els visuals assignats.
