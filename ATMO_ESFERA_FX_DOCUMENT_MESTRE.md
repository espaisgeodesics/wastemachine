# ATMO ESFERA FX
## DOCUMENT MESTRE DE PRODUCTE, ARQUITECTURA I DESENVOLUPAMENT PER A CODEX

**Nom públic:** ATMO ESFERA FX  
**Lema:** L'espai es converteix en instrument.  
**Projecte d'origen:** Wasteland Machine  
**Repositori:** `espaisgeodesics/wastemachine`  
**Entorn inicial:** Windows 10, Python 3.12  
**Idioma principal de la interfície:** català

---

# 1. OBJECTIU GENERAL

Volem transformar l'actual Wasteland Machine en **ATMO ESFERA FX**, una plataforma de creació d'experiències interactives, audiovisuals, musicals, educatives, artístiques i lúdiques.

No volem desenvolupar un únic espectacle.

Volem construir **l'eina que permeti crear molts espectacles, exposicions, jocs i instal·lacions diferents sense reprogramar el sistema per a cada projecte**.

La plataforma ha de funcionar inicialment en dos formats:

1. **DOME:** cúpula geodèsica immersiva, amb participants que es desplacen físicament.
2. **TABLE:** taula interactiva amb objectes o targetes, inspirada en el concepte Reactable.

El motor de detecció, les regles, l'àudio, el MIDI, les escenes i els continguts han de ser compartits sempre que sigui possible.

Els dos formats tindran configuracions pròpies de càmera, calibració, superfície i projecció.

---

# 2. DECISIÓ FÍSICA FONAMENTAL: MARCADORS ALS BARRETS

## 2.1. Com es detectaran els participants

Aquesta és una decisió confirmada del projecte.

**Cada participant portarà un barret, casc lleuger o suport similar amb un marcador ArUco fixat a la part superior.**

La càmera estarà instal·lada:

- Al centre superior de la cúpula geodèsica.
- Orientada verticalment cap avall, sempre que la instal·lació ho permeti.
- Amb un camp de visió que intenti cobrir tota la superfície interactiva.

Així, quan les persones es desplacin per l'espai, la càmera podrà identificar els marcadors dels seus barrets.

Cada marcador tindrà un ID únic.

Per exemple:

- ArUco ID 0: participant 1.
- ArUco ID 1: participant 2.
- ArUco ID 2: participant 3.
- ArUco ID 3: participant 4.
- ArUco ID 4: participant 5.

El sistema actual admet 16 identificadors, del 0 al 15.

No pressuposem que els 16 es puguin detectar simultàniament amb garanties fins que no es facin proves físiques.

## 2.2. Identitat persistent

Cada participant ha de conservar el mateix identificador durant la sessió.

El sistema ha de poder mostrar:

- ID ArUco.
- Nom o àlies del participant.
- Color identificatiu a la pantalla de control.
- Posició X/Y.
- Orientació del marcador.
- Zona actual.
- Estat de detecció.
- Temps des de l'última detecció.
- Estat de joc, si escau.

Cal separar el concepte de **marcador físic** del concepte de **participant**.

Un marcador pot representar una persona en un escape room o un objecte musical en el mode Table.

## 2.3. Limitacions òptiques importants

La posició del marcador al barret no coincideix exactament amb la posició dels peus.

Amb una càmera en perspectiva, els marcadors situats a una alçada superior al terra poden presentar un desplaçament aparent, especialment lluny del centre de la imatge.

Per tant:

- No aplicar directament una homografia del pla del terra a les coordenades dels barrets assumint precisió absoluta.
- Estudiar una calibració específica del pla aproximat dels marcadors.
- Considerar l'alçada de la càmera, l'alçada dels participants i la perspectiva.
- Valorar una correcció geomètrica basada en un model de càmera calibrat.
- Documentar els errors esperables.
- Fer proves amb persones de diferents alçades.
- Introduir marges de tolerància a les fronteres de les zones.
- No presentar la detecció com a infal·lible.

El sistema no ha de donar per fet que la càmera sempre veu tots els barrets.

Hi pot haver ocultacions, inclinacions, reflexos, moviment ràpid, marcadors massa petits o zones fora del camp visual.

## 2.4. Disseny dels barrets

Preveure proves amb:

- Marcadors de mida adequada a la resolució de la càmera.
- Impressió de contrast elevat.
- Superfície plana i rígida.
- Fixació estable.
- Orientació preferentment horitzontal.
- Materials còmodes i segurs.
- Barrets lleugers, sense elements que sobresurtin perillosament.

Evitar suports que puguin enganxar-se a l'estructura de la cúpula.

La rotació del marcador pot servir com a control interactiu, però cal tenir en compte que el moviment del cap no sempre equival a una intenció de control musical.

---

# 3. PUNT DE PARTIDA REAL: WASTELAND MACHINE

Abans de modificar res, inspecciona el repositori i el codi existent.

La darrera versió de referència del desenvolupament és **Wasteland Machine 4.5.15, pas 15**, sempre que sigui efectivament la versió disponible al repositori.

El programa actual utilitza:

- Python 3.12.
- Tkinter.
- OpenCV amb suport ArUco.
- NumPy.
- Pillow.
- Mido.
- python-rtmidi.
- loopMIDI.
- Cakewalk Sonar com a receptor MIDI habitual.

Funcions existents en la versió de referència:

- Detecció de 16 marcadors ArUco, IDs 0–15.
- Nota MIDI.
- Harmonia espacial.
- Arpegiador espacial.
- Control MIDI CC.
- Canvi visual.
- Tempo.
- Cap acció.
- Editor de targetes.
- Configuració desplegable d'harmonia i arpegiador.
- BPM intern.
- Finestra de càmera.
- Previsualització visual.
- Finestra de connexió MIDI.
- Finestra de projecció.
- Distribució de finestres configurable.
- Desament de projectes o configuracions JSON.

El programa disposa d'una estètica industrial pròpia i una capçalera gràfica.

**No eliminar ni trencar aquestes funcions.**

No assumir que les noves funcionalitats descrites més avall ja estan implementades.

El BPM intern no està necessàriament sincronitzat amb el transport de Cakewalk.

Existeix una qüestió pendent de verificació: el control remot de Mute d'una pista d'àudio de Cakewalk pot activar-se amb un marcador però no recuperar l'estat esperat quan el marcador desapareix. Cal diagnosticar el flux Note On/Note Off i el comportament del receptor abans d'afirmar-ne la causa.

---

# 4. ARQUITECTURA QUE VOLEM

ATMO ESFERA FX ha de separar, progressivament, aquests subsistemes:

1. **Captura:** càmeres i imatges.
2. **Detecció:** marcadors ArUco i qualitat de detecció.
3. **Seguiment:** participants, posicions, rotacions i pèrdues temporals.
4. **Calibració:** transformació de coordenades.
5. **Espai:** superfícies, graelles, zones i geometria.
6. **Esdeveniments:** entrada, sortida, moviment, rotació, aparició i desaparició.
7. **Regles:** condicions i accions configurables.
8. **Àudio:** sons, ambients, capes, volums i transicions.
9. **MIDI:** notes, CC, harmonies, arpegis i Kaoss XY.
10. **Visuals:** colors, imatges, escenes i projecció.
11. **Jocs:** estats, objectius, puntuacions, penalitzacions i temps.
12. **Projectes:** experiències, recursos, configuracions i versions.
13. **Interfície:** editors i control de l'operador.
14. **Simulació:** proves sense càmera ni participants reals.
15. **Diagnòstic:** registres, avisos i eines de verificació.

No cal implementar tots aquests mòduls de cop.

Primer cal definir-ne les responsabilitats i les interfícies.

---

# 5. DOS PERFILS DE FUNCIONAMENT

## 5.1. DOME

El perfil Dome està pensat per a una cúpula geodèsica.

Característiques:

- Càmera superior central.
- Participants amb marcadors ArUco als barrets.
- Superfície interactiva circular o aproximadament circular.
- Zones físiques del terra.
- Possibilitat de diversos participants simultanis.
- Projecció immersiva.
- Àudio ambiental.
- Experiències cooperatives.
- Jocs d'exploració i moviment.

La zona de joc ha de poder delimitar-se independentment de la forma total de la imatge de càmera.

## 5.2. TABLE

El perfil Table està pensat per a una taula interactiva.

Característiques:

- Càmera adequada al muntatge.
- Marcadors ArUco sobre objectes o peces.
- Superfície rectangular o circular.
- Control musical i audiovisual amb posició i rotació.
- Interaccions entre objectes.
- Calibració pròpia.
- Possibilitat de projecció sobre la taula.

## 5.3. Reutilització

El mateix sistema de regles ha de poder interpretar:

«El marcador 4 entra a la zona 7»

independentment de si el marcador està sobre un barret o sobre un objecte.

El perfil físic decideix com es detecta i es calibra la posició.

L'experiència decideix què significa aquell esdeveniment.

---

# 6. GESTOR D'EXPERIÈNCIES

La pantalla inicial ha de permetre:

- Crear una experiència.
- Obrir-ne una d'existent.
- Duplicar-la.
- Desar-la.
- Exportar-la.
- Importar-la.
- Seleccionar Dome o Table.
- Escollir una plantilla.
- Obrir l'editor de l'experiència.
- Iniciar una sessió.
- Aturar-la de manera segura.

Exemples de projectes:

- BOSC VIU.
- LABORATORI MUSICAL.
- MEMÒRIA DEL TERRITORI.
- EL BOTÍ.
- PROJECTE EN BLANC.

Cada experiència ha de conservar els seus recursos i la seva configuració.

Preveure un format de projecte versionat i un manifest de recursos.

Preferir rutes relatives per facilitar el trasllat entre ordinadors.

Gestionar els fitxers que falten sense provocar una fallada completa.

Mantenir compatibilitat amb els projectes JSON actuals o proporcionar un mecanisme de migració segur.

---

# 7. EDITOR DE SUPERFÍCIES I ZONES

Crear un editor visual de l'espai.

## 7.1. Primera versió

Graella inicial de 8 × 8, amb 64 caselles.

Ha de permetre:

- Veure el mapa de la superfície.
- Activar o desactivar caselles.
- Agrupar caselles en zones.
- Posar nom a les zones.
- Assignar colors d'edició.
- Associar sons i imatges.
- Autoritzar marcadors concrets.
- Configurar accions.
- Crear, editar i eliminar zones.
- Desar la configuració.
- Visualitzar les posicions detectades.

En el mode Dome, ignorar o marcar les caselles que queden completament fora de la superfície circular útil.

## 7.2. Comportaments de zona

**Puntual:** l'acció s'executa una vegada quan el marcador entra.

**Contínua:** l'acció es manté mentre el marcador hi és.

**Persistent:** l'acció continua després que el marcador surti.

**Entrada/sortida:** es poden definir accions diferents per a cadascun dels dos esdeveniments.

La persistència és especialment important per a les fotografies d'exposicions.

## 7.3. Estabilitat

Implementar:

- Confirmació d'entrada durant diversos fotogrames o temps mínim.
- Histèresi a les fronteres.
- Filtratge de soroll.
- Tractament de pèrdues breus de detecció.
- Evitar activacions repetides.
- Resolució de conflictes entre zones.

La detecció d'una casella no ha de canviar contínuament per petits moviments de la imatge.

---

# 8. SEGUIMENT DE PARTICIPANTS

Aquest apartat és especialment important per al mode Dome.

## 8.1. Registre de participants

Permetre registrar una sessió amb, per exemple, cinc jugadors.

Cada jugador tindrà:

- Identificador intern.
- ID ArUco assignat.
- Nom opcional.
- Color identificatiu.
- Estat de presència.
- Zona actual.
- Posició actual.
- Historial recent.
- Estat de joc.

## 8.2. Detecció simultània

En cada fotograma, processar tots els marcadors detectats.

No limitar el programa a un únic marcador actiu.

Cada participant ha de tenir el seu estat independent.

Si diversos participants entren en zones diferents al mateix temps, el sistema ha de generar els esdeveniments corresponents sense perdre'n cap.

## 8.3. Pèrdua de detecció

Distingir:

- Marcador detectat.
- Marcador temporalment perdut.
- Marcador absent durant un temps prolongat.
- Participant retirat de la sessió.

No interpretar automàticament una pèrdua de càmera com una eliminació del joc.

El comportament ha de ser configurable.

## 8.4. Regles de moviment

Poder detectar:

- Entrada en zona.
- Sortida de zona.
- Permanència.
- Desplaçament.
- Canvi d'orientació.
- Proximitat entre participants.
- Reunió de diversos participants en una zona.
- Arribada a un objectiu.

La posició i l'orientació han d'estar expressades en un sistema de coordenades coherent.

---

# 9. MOTOR D'ESDEVENIMENTS I REGLES

Aquest serà el cor de la plataforma.

La lògica ha de seguir el model:

**SI passa una condició → LLAVORS executa una o més accions.**

Exemples:

- SI el jugador 1 entra a la zona RIU → activa el so del riu.
- SI el jugador 2 entra a la zona OCELLS → activa un cant d'ocell.
- SI una targeta gira → modifica un CC MIDI.
- SI un jugador entra en una trampa → activa l'alarma.
- SI tots els jugadors arriben a l'objectiu → activa la victòria.
- SI dos marcadors s'apropen → mostra una nova escena.
- SI una fotografia s'activa → mantén-la fins a una altra ordre.
- SI comença una alarma → atura o redueix els ocells.

## 9.1. Activadors

Preveure:

- Aparició de marcador.
- Desaparició confirmada.
- Entrada en zona.
- Sortida de zona.
- Permanència.
- Moviment.
- Rotació.
- Proximitat.
- Temps transcorregut.
- Inici de sessió.
- Final de sessió.
- Canvi d'estat de joc.
- Activació manual de l'operador.

## 9.2. Accions

Preveure:

- Reproduir so.
- Aturar so.
- Canviar volum.
- Fer una transició sonora.
- Projectar imatge.
- Canviar color.
- Activar escena.
- Enviar nota MIDI.
- Enviar MIDI CC.
- Modificar una variable.
- Afegir penalització.
- Restar una vida.
- Mostrar missatge.
- Activar temporitzador.
- Pausar partida.
- Declarar victòria.
- Declarar derrota.

## 9.3. Prioritats

Definir què passa quan dues regles donen ordres contradictòries.

Per exemple:

- Una regla vol projectar una fotografia.
- Una altra vol projectar color vermell.
- Una tercera vol mostrar una alarma.

Cal un mecanisme explícit de prioritats, capes o control de propietat de la sortida.

No deixar el resultat a l'ordre accidental dels fotogrames.

---

# 10. EXPERIÈNCIA 1: BOSC VIU

Objectiu: crear la sensació d'entrar en un entorn natural.

## Ambient inicial

- Ocells.
- Vent.
- Fulles.
- Riu.
- Imatges de bosc.

## Interaccions

Zona OCELLS:

Quan un participant hi entra, s'activa un cant d'ocell.

Zona RIU:

Quan s'hi acosta, augmenta gradualment el so de l'aigua.

Zona VENT:

El moviment o la posició modifica la intensitat del vent.

Zona CLARIANA:

Canvia la imatge projectada.

## Escena especial

En una determinada situació, una targeta activa una alarma o un efecte cinematogràfic de tret.

En aquell moment:

- Sona l'efecte.
- Els ocells callen o es reprodueix un efecte d'ocells que fugen.
- Canvia l'ambient visual.
- Es pot iniciar una nova fase.

Tot ha de poder configurar-se des de l'editor de regles.

---

# 11. EXPERIÈNCIA 2: LABORATORI MUSICAL

Objectiu: crear música mitjançant moviment espacial.

Aprofitar:

- Notes MIDI.
- Harmonia espacial.
- Arpegiador espacial.
- Controls CC.
- Tempo.
- Canvis visuals.

Permetre diversos participants o objectes musicals.

Exemples:

- Un participant controla una melodia.
- Un altre controla un baix.
- Un altre controla filtres.
- Un altre controla una seqüència.
- Un altre controla els colors.

Les funcions han de ser assignables, no imposades a IDs fixos.

Mantenir la comunicació amb Cakewalk Sonar mitjançant loopMIDI.

---

# 12. KAOSS XY ESPACIAL

Crear una nova funció configurable anomenada **Kaoss XY espacial**.

Utilitza:

- X.
- Y.
- Rotació.

Té dos modes.

## 12.1. Instrument

Genera notes MIDI.

X pot controlar les notes d'una escala.

Y pot controlar velocitat, brillantor o un altre paràmetre.

La rotació pot controlar un CC addicional.

Incloure:

- Nota fonamental.
- Escala.
- Canal MIDI.
- Rang de notes.
- Quantització.
- Suavització.
- Gestió de Note On/Off.
- Comportament en desaparèixer el marcador.

## 12.2. Efectes

No genera notes.

Envia MIDI CC per transformar sons existents.

Els efectes depenen de les assignacions del sintetitzador o de Cakewalk.

## 12.3. Quatre patrons preparats

**ATMOSFERA**

- Mode: Instrument.
- X: notes d'escala.
- Y: CC 74.
- Rotació: CC 11.

**PULSACIÓ**

- Mode: Instrument.
- X: notes d'escala.
- Y: velocitat MIDI.
- Rotació: CC 74.

**TRANSFORMACIÓ**

- Mode: Efectes.
- X: CC 74.
- Y: CC 1.
- Rotació: CC 11.

**ÒRBITA**

- Mode: Efectes.
- X: CC 10.
- Y: CC 11.
- Rotació: CC 1.

Els patrons han de ser seleccionables des d'un desplegable.

L'usuari ha de poder personalitzar-los i desar-los.

En mode Dome, considerar que el moviment del cap pot provocar oscil·lacions no desitjades dels controls. Incorporar zones mortes, suavització i possibilitat de desactivar la rotació.

---

# 13. EXPERIÈNCIA 3: MUSEU INTERACTIU

Objectiu: crear exposicions explorables.

Exemple: història d'un poble.

Zones:

- Fotografia antiga.
- Mapa històric.
- Entrevista sonora.
- Document.
- Vídeo en una fase posterior.

Quan un participant entra en una zona, s'activa el contingut corresponent.

## Persistència visual

Una fotografia ha de poder continuar projectada després que el participant surti de la zona.

Només canviarà quan una altra regla o escena ho indiqui.

## Editor

L'usuari ha de poder associar:

- Imatge.
- So.
- Títol.
- Text.
- Zona.
- Participants autoritzats.
- Condicions d'activació.

Els textos públics només s'han de mostrar quan l'experiència els requereixi.

---

# 14. EXPERIÈNCIA 4: ESCAPE ROOM — EL BOTÍ

Aquesta és una de les demostracions més importants.

## 14.1. Escenari

Una cúpula geodèsica amb dues portes o accessos.

Un grup de cinc persones entra per un costat.

A l'altre extrem hi ha una bossa amb un botí fictici.

Els participants han d'arribar a l'objectiu evitant zones perilloses invisibles.

Tots porten un barret amb un marcador ArUco.

La càmera superior observa les seves posicions.

## 14.2. Zones

- Entrada.
- Zones segures.
- Zones perilloses.
- Zones de pista.
- Zona d'objectiu.
- Sortida narrativa.

Les zones perilloses poden ser invisibles per als jugadors però visibles per a l'operador.

## 14.3. Inici

Comença un ambient tranquil:

- Ocells.
- Vent.
- Sons de natura.

Els participants reben una missió.

## 14.4. Trampa

Quan un participant entra en una zona perillosa confirmada:

1. Es registra l'esdeveniment.
2. S'activa una alarma.
3. Sona un efecte cinematogràfic de tret, si està configurat.
4. Els ocells callen o fugen.
5. Canvia la projecció.
6. S'aplica la penalització configurada.

Les penalitzacions possibles:

- Pèrdua d'una vida.
- Pèrdua de temps.
- Retorn a un punt de control.
- Alarma temporal.
- Derrota de l'equip.

## 14.5. Victòria

La victòria pot requerir:

- Arribar a la zona del botí.
- Que hi arribin tots els participants.
- Que hi arribin determinats participants.
- Completar una sèrie de proves.
- Complir un límit de temps.

Les condicions han de ser configurables.

## 14.6. Estats

- Preparat.
- Compte enrere.
- En curs.
- Pausat.
- Alarma.
- Victòria.
- Derrota.
- Reinici.

## 14.7. Operador

La pantalla de control ha de mostrar:

- Posicions dels cinc participants.
- Zones perilloses.
- Estat de cada participant.
- Temps restant.
- Penalitzacions.
- Estat general de la partida.

Ha de permetre:

- Iniciar.
- Pausar.
- Reiniciar.
- Desactivar temporalment una trampa.
- Anul·lar una penalització errònia.
- Declarar una incidència de seguiment.
- Finalitzar la sessió.

## 14.8. Seguretat

Les portes han de romandre físicament accessibles.

Cap derrota virtual ha de bloquejar una sortida real.

No fer servir làsers perillosos ni efectes que puguin provocar lesions.

Els efectes sonors han de tenir nivells segurs i configurables.

Les zones perilloses són elements virtuals del joc.

Com que la càmera observa marcadors als barrets, cal validar la precisió de les zones abans d'utilitzar-les per penalitzar jugadors.

En cas de detecció dubtosa, és preferible no aplicar una penalització irreversible automàticament.

---

# 15. EXPERIÈNCIA 5: ACTIVITATS COOPERATIVES

Permetre experiències educatives i col·lectives.

Exemples:

- Cinc persones creen una composició musical.
- Un grup reconstrueix una història.
- Dos participants han de coincidir en zones diferents.
- Diversos jugadors han d'activar punts en un ordre concret.
- Una exposició es desbloqueja cooperativament.
- Es resol un enigma espacial.

Les regles han de poder consultar l'estat de diversos participants.

---

# 16. MOTOR D'ÀUDIO

Actualment Wasteland Machine treballa principalment amb MIDI.

ATMO ESFERA FX necessita també reproducció d'àudio independent.

Estudiar una solució estable per a Windows que permeti:

- Reproduir fitxers d'àudio.
- Reproduir diversos sons simultanis.
- Fer bucles.
- Controlar volums independents.
- Fer fades d'entrada i sortida.
- Llançar efectes puntuals.
- Mantenir ambients de fons.
- Aturar grups de sons.
- Gestionar escenes sonores.

Exemples:

BOSC VIU:

- Capa d'ocells.
- Capa de vent.
- Capa de riu.

EL BOTÍ:

- Ambient inicial.
- Alarma.
- Efecte de tret.
- Ocells fugint.
- Música de victòria.

No bloquejar Tkinter durant la reproducció.

No eliminar ni substituir obligatòriament la sortida MIDI actual.

Permetre utilitzar Cakewalk quan sigui convenient i àudio intern quan sigui més pràctic.

---

# 17. MOTOR VISUAL

Separar estrictament dues sortides.

## 17.1. Operador

Pot veure:

- Càmera.
- Graella.
- Zones.
- IDs.
- Participants.
- Alertes.
- Estat del joc.
- Mapes musicals.
- Controls.

## 17.2. Públic

Només ha de veure el contingut de l'experiència.

Modes inicials:

- Color uniforme.
- Imatge fixa.
- Escena visual.
- Missatge públic configurat.

Vídeo i composicions avançades en fases posteriors.

## 17.3. Regla del color

En mode cromàtic, la projecció ha de continuar mostrant únicament un color uniforme.

Sense quadrícules, números, textos tècnics ni indicadors.

## 17.4. Imatges persistents

Si una zona activa una fotografia, aquesta pot quedar visible fins a una altra ordre.

No recarregar el fitxer d'imatge a cada fotograma.

Preparar una gestió de recursos eficient.

---

# 18. SIMULADOR INTEGRAT

Crear un mode de proves sense càmera.

El simulador ha de permetre:

- Crear participants virtuals.
- Assignar IDs.
- Moure'ls per una superfície.
- Simular rotacions.
- Simular entrades i sortides de zones.
- Simular pèrdues de detecció.
- Executar regles.
- Veure un registre d'esdeveniments.
- Provar canvis d'imatge.
- Provar àudio.
- Provar Kaoss XY.
- Provar victòria i derrota.

Per al joc EL BOTÍ, poder simular cinc jugadors simultanis.

Aquest simulador és fonamental per desenvolupar sense muntar la cúpula cada vegada.

---

# 19. CALIBRACIÓ I PROVES FÍSIQUES

Preveure un assistent de calibració.

## Dome

- Configurar superfície útil.
- Definir centre i límits.
- Comprovar cobertura de càmera.
- Calibrar coordenades.
- Validar posicions amb participants reals.
- Mesurar errors en diversos punts.
- Verificar alçades diferents.
- Comprovar inclinacions dels barrets.
- Comprovar els marges de les zones.
- Detectar punts cecs.

## Table

- Definir superfície.
- Calibrar les cantonades o els punts de referència.
- Comprovar coordenades.
- Validar rotació.
- Comprovar la precisió als extrems.

No donar per resolta la precisió només perquè OpenCV detecta correctament un marcador.

La detecció visual i la localització física són problemes relacionats però diferents.

---

# 20. INTERFÍCIE I IDENTITAT

La nova marca pública serà:

**ATMO ESFERA FX**

Estètica suggerida:

- Tecnològica.
- Immersiva.
- Atmosfèrica.
- Geomètrica.
- Clara i llegible.
- Adequada per a un operador en directe.

No fer el canvi de noms interns de Python precipitadament.

Conservar temporalment els identificadors i fitxers necessaris per mantenir la compatibilitat.

Pantalles futures:

1. Gestor d'experiències.
2. Dome / Table.
3. Càmera i calibració.
4. Participants i marcadors.
5. Zones espacials.
6. Regles.
7. Sons.
8. MIDI i instruments.
9. Kaoss XY.
10. Visuals.
11. Jocs.
12. Simulador.
13. Diagnòstic.

No cal construir totes les pantalles de cop.

---

# 21. ROBUSTESA

El programa ha de poder funcionar en instal·lacions públiques.

Requisits:

- Interfície responsiva.
- Gestió correcta de fils.
- Càmera recuperable després d'una desconnexió.
- MIDI recuperable després d'una desconnexió.
- Notes MIDI sense quedar penjades.
- Sons que es puguin aturar de manera segura.
- Fitxers inexistents gestionats.
- Projectes desats correctament.
- Registre d'errors.
- Control d'esdeveniments repetits.
- Memòria i CPU controlades.
- Evitar recàrregues constants de recursos.
- Reinici segur de sessions.
- Cap dependència obligatòria d'internet per executar una instal·lació local.

---

# 22. PROVES AUTOMÀTIQUES I CRITERIS D'ACCEPTACIÓ

Crear proves, sempre que sigui possible, per verificar:

## Seguiment

- Dos marcadors diferents mantenen identitats independents.
- Cinc participants poden tenir estats simultanis.
- Una pèrdua breu no genera automàticament una derrota.
- El retorn d'un marcador no duplica indegudament les accions.

## Zones

- Entrada correcta.
- Sortida correcta.
- Persistència.
- No repetició innecessària.
- Gestió de fronteres.
- Zones autoritzades per ID.

## MIDI

- Note On.
- Note Off.
- Canvi de nota.
- Desaparició del marcador.
- CC sense saturació.
- Kaoss XY.
- Cap nota penjada.

## Visuals

- Color uniforme net.
- Imatge persistent.
- Canvi d'escena.
- Prioritats de sortida.
- Fitxers inexistents.

## Jocs

- Inici.
- Pausa.
- Penalització.
- Victòria.
- Derrota.
- Reinici.
- Diversos participants.
- No penalitzar per una pèrdua dubtosa de detecció.

## Projectes

- Desar.
- Obrir.
- Duplicar.
- Migrar configuracions antigues.
- Detectar recursos absents.

Distingir proves automàtiques de proves que necessiten càmera, barrets, projector, Cakewalk o instal·lació real.

---

# 23. PLA DE DESENVOLUPAMENT PROGRESSIU

## FASE 0 — AUDITORIA

Examinar el codi real.

Documentar què funciona i què falta.

No reescriure massivament.

## FASE 1 — MODEL COMÚ DE DETECCIÓ I ESDEVENIMENTS

Separar la detecció ArUco de les accions musicals.

Crear un model d'estat per marcador o participant.

## FASE 2 — SIMULADOR

Simular cinc participants i les seves posicions.

## FASE 3 — SUPERFÍCIES I ZONES

Crear el mapa 8 × 8 i les zones configurables.

## FASE 4 — MOTOR DE REGLES

Connectar esdeveniments i accions.

## FASE 5 — ÀUDIO I IMATGES

Crear la primera experiència BOSC VIU.

## FASE 6 — KAOSS XY

Implementar els dos modes i quatre patrons.

## FASE 7 — MOTOR DE JOC

Crear EL BOTÍ amb cinc participants simulats.

## FASE 8 — CALIBRACIÓ DOME

Provar la càmera superior i els barrets ArUco.

## FASE 9 — PERFIL TABLE

Adaptar el motor a la taula.

## FASE 10 — GESTOR COMPLET D'EXPERIÈNCIES

Plantilles, importació, exportació i edició avançada.

## FASES FUTURES

- Vídeo.
- Transicions visuals.
- Àudio espacial.
- Múltiples càmeres.
- Múltiples projectors.
- Detecció de persones sense marcadors.
- OSC.
- Integració amb Resolume o TouchDesigner.
- Experiències més complexes.

L'ordre es pot ajustar després de l'auditoria.

---

# 24. INSTRUCCIONS DE TREBALL PER A CODEX

IMPORTANT:

1. Inspecciona el repositori abans de proposar canvis.
2. Verifica quina versió del programa hi ha realment.
3. No confonguis funcions existents amb idees futures.
4. No eliminis cap funció musical actual.
5. No trenquis la projecció cromàtica neta.
6. Mantingues el funcionament MIDI actual.
7. No assumeixis precisió perfecta dels marcadors als barrets.
8. No assumeixis que una única càmera elimina totes les ocultacions.
9. Dissenya per a múltiples participants simultanis.
10. Separa les dades de les experiències del codi.
11. Proposa una arquitectura modular però sense complexitat innecessària.
12. Fes increments petits.
13. Afegeix proves.
14. Explica els canvis en català.
15. Proporciona instruccions clares per a Windows i PowerShell.
16. Quan es lliuri una versió, inclou el codi complet i els recursos necessaris.
17. Conserva una versió estable recuperable.
18. No facis una reescriptura massiva sense aprovació.

---

# 25. QUÈ ET DEMANEM ARA

CODEX, abans de programar noves funcions, prepara un informe amb:

**A. Inventari del codi existent**

Quins components es poden reutilitzar?

**B. Arquitectura proposada**

Com separaries captura, seguiment, zones, regles, àudio, MIDI, visuals i projectes?

**C. Anàlisi específica del sistema de barrets**

Quines limitacions té una càmera superior central?

Com recomanes calibrar la posició dels marcadors situats damunt dels caps?

Quines proves físiques necessitem?

**D. Estratègia de compatibilitat**

Com mantindrem el Wasteland Machine actual funcionant durant la transformació?

**E. Full de ruta**

Quina seqüència de desenvolupament és més segura i eficient?

**F. Primera tasca concreta**

Proposa un primer increment petit, verificable i reversible, amb proves i criteris d'acceptació.

**G. Decisions pendents**

Enumera únicament les dades físiques o funcionals que necessites conèixer per avançar amb seguretat.

**NO comencis encara una reescriptura completa. Espera l'aprovació de l'arquitectura i de la primera fase.**

---

# 26. VISIÓ FINAL

ATMO ESFERA FX ha de permetre:

- Entrar en un bosc que respon als moviments de les persones.
- Sentir ocells, rius i vent que canvien segons la posició.
- Crear música electrònica amb el cos i amb objectes.
- Transformar sons amb un Kaoss XY espacial.
- Descobrir exposicions de museu caminant.
- Activar fotografies, narracions i escenes.
- Participar en escape rooms amb zones invisibles.
- Jugar cooperativament amb cinc persones o més, segons la capacitat real del sistema.
- Adaptar la mateixa tecnologia a una cúpula o a una taula.
- Crear experiències noves des d'un editor visual.

La tecnologia ha de ser robusta, però l'experiència de l'usuari ha de semblar màgica.

**No volem només un programa de detecció ArUco.**

**Volem una plataforma per convertir espais físics en mons interactius.**

# ATMO ESFERA FX
## L'espai es converteix en instrument.