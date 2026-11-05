# ATMO ESFERA FX — fase 3: zones al flux comú

Entrega: **Wasteland Machine 4.7.8**, sobre la [fase 2, 4.7.7](ATMO_ESFERA_FX_FASE_2.md),
commit recuperable `6fc9e6c`, a `codex/wasteland-camera-windows-launcher`.

## Què incorpora

El flux comú d’observacions ja pot informar de la zona de cada marcador i
generar **totes** les entrades i sortides confirmades d’un fotograma. És
independent de la funció musical de la targeta: un marcador configurat com a
Nota MIDI o Cap acció també pot generar esdeveniments espacials si està
autoritzat a la zona. No cal convertir-lo en Activar zona espacial per
observar-lo al nou flux.

La columna **Zona** del registre de participants mostra el nom de la zona
confirmada. Quan l’observació o la font no són actuals, la zona s’indica com
a «antiga». Sense homografia vàlida mostra **Sense calibració** i no genera
entrades. L’última posició de càmera continua diferenciada de la posició
transformada al pla de terra.

El registre comú afegeix `zone_entered` i `zone_exited`, amb ID i nom de zona,
font, marcador, participant vinculat, temps, seqüència de fotograma i motiu:

- `movement` / **Moviment**: transició espacial confirmada.
- `missing` / **Pèrdua**: sortida confirmada a partir d’imatges vàlides sense
  el marcador.
- `detection_gap` / **Revalidació**: el motor existent invalida una confirmació
  quan una detecció torna després d’un interval massa llarg. Requereix tornar
  a confirmar l’entrada; no és una penalització ni una prova de moviment físic.

Les avaries de font no es processen com un fotograma vàlid buit i no generen
sortides només perquè passi el temps. Conserven zones antigues amb
`observed=False` i `source_available=False`. Quan retorna una imatge vàlida,
es reprèn la lògica existent, inclosa la revalidació per interval de detecció.
No s’elimina cap participant ni s’executen regles de joc.

## Proves al simulador, sense dispositius

1. Configura les zones amb l’editor existent o obre un projecte amb zones.
2. Obre **Participants → Simulador de cinc participants…**.
3. Prem **CARREGAR ZONES DEL PROJECTE**. Es copia el mapa a la sessió virtual;
   no es modifiquen el projecte ni la calibració real.
4. A **Mapa i moviment**, desplaça els participants per les caselles. Les zones
   habilitades i el contorn circular apareixen sobre la superfície virtual.
   Respecta els IDs autoritzats de cada zona, ID 0 = targeta 01.
5. Consulta **Participants i esdeveniments** per veure zones confirmades,
   entrades, sortides i motius. Pots provar cinc persones simultànies,
   ocultacions, avaries, retirada i recuperació.

La còpia utilitza una **calibració sintètica identitat**, només per al simulador:
les coordenades normalitzades virtuals es transformen al mapa virtual sense
reutilitzar l’homografia de la càmera física. Això no valida la precisió de
terra, peus o barrets ni calibra la instal·lació.

Les modificacions posteriors al mapa real requereixen tornar a carregar-ne
la còpia. **REINICIAR PROVA** conserva el mapa virtual carregat, reinicia els
cinc participants i buida els estats i esdeveniments virtuals. Les imatges
referenciades a les zones no es carreguen ni es projecten des del simulador.

## Arquitectura i compatibilitat

`common_spatial.py` adapta `ObservationFrame` al **mateix `SpatialEngine`**
existent. Manté un motor independent per font, amb les mateixes autoritzacions,
caselles, histèresi, retard d’entrada/sortida, mínim de deteccions i límit
d’interval. No duplica el detector ArUco ni rellegeix la càmera.

`CommonZoneState` és immutable: font, marcador, zona i nom, posició de terra,
observació actual, disponibilitat, calibració i temps. Les instantànies són
de només lectura; per defecte hi ha com a màxim quatre fonts i setze marcadors
per font. Temps i seqüències no creixents es rebutgen abans de modificar l’estat.
Canviar el mapa o obrir un projecte reinicia les confirmacions espacials;
un desament sense canvis conserva les confirmacions. Reinicialitzar el mapa
és una operació de configuració, no una sortida de zona per moviment.

`CommonEventLog` incorpora el lot espacial complet, en ordre estable, i evita
repetir el mateix fotograma. El límit d’historial no retalla el lot retornat.
Les autoritzacions continuen referides al marcador; la identitat del participant
s’afegeix a l’esdeveniment en el moment de crear-lo. Reassignar una persona o
canviar el nom d’una zona no reescriu l’historial.

**L’adaptador és passiu respecte de les sortides.** El motor de projecció
existent continua activant les fotografies només per les targetes amb funció
Activar zona espacial i conserva persistència, presència i retard després de
sortir. Les targetes musicals no projecten una fotografia nova només perquè
ara generin esdeveniments de zona. El color, MIDI, Mute i els temporitzadors
musicals mantenen el comportament anterior; no hi ha dues rutes enviant
la mateixa acció. La fase 4 connectarà regles declaratives a aquests
esdeveniments amb propietat i prioritat de sortides explícites.

Els errors del nou observador continuen continguts al diagnòstic limitat
de seguiment. El simulador té motor, participants i registre independents.
No s’han modificat `SpatialEngine`, el reproductor de fotografies ni les
declaracions de dependències. No hi ha cap migració de projecte: els estats
de zona i esdeveniments són de sessió, no dades persistides al JSON.

## Validació

**171 proves correctes, cap omesa**, amb Python 3.12, pantalla virtual Xorg i
les versions de `requirements.txt`. Les 157 proves de la fase 2 també s’han
executat després de connectar l’adaptador, abans d’afegir les proves noves.

```text
python -m unittest discover -s tests -v
```

Es comproven cinc entrades simultànies sense perdre els esdeveniments que no
guanyen la projecció, paritat exacta d’esdeveniments amb `SpatialEngine`,
autoritzacions, histèresi, sortida confirmada, transformació de calibració,
mapa no calibrat, avaria, recuperació, fonts independents, instantànies
immutables, límits, reconfiguració, deduplicació i noms al registre.

La integració usa cinc marcadors ArUco sintètics amb funció musical: tots
generen entrades de zona, envien una sola nota cadascun i no projecten la
fotografia del mapa. Es comparen els missatges MIDI i els arrays públics
amb l’observador activat/desactivat, també injectant-li una excepció.
Una prova específica compara fotografies i seqüències de modes exactes
en **persistent, presence i after_exit**, incloses retirada i nova entrada.
També s’ha comprovat el bucle real de Tkinter amb cinc entrades simultànies,
els noms de zona i el registre visibles al simulador, les sortides reals
intactes i el tancament normal de l’aplicació.

Per instal·lar una altra vegada caldrà el paquet complet, inclòs
`common_spatial.py`, comprovat pel BAT general. El punt de recuperació anterior
és `6fc9e6c` amb el projecte original. La validació física de Windows, càmera,
barrets, projector, loopMIDI i Sonar continua pendent; aquesta fase es pot
desenvolupar i provar completament al núvol amb entrades sintètiques.
