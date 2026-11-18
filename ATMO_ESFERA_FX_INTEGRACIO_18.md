# ATMO ESFERA FX · Integració 18

Branca: `atmo/interficie-primera-integracio`. Base: integració 17, validada per l’usuari.
Descomprimeix el ZIP complet en una carpeta nova i obre **OBRIR_ATMO.bat** (Python 3.12). No cal desinstal·lar res.

## Calibrar el terra

El botó **CALIBRAR EL TERRA** és accessible al motor i a la previsualització.

1. Obre la càmera, tria la forma real del terra i congela la imatge.
2. Cercle: marca NORD, EST, SUD i OEST del perímetre. Quadrat o rectangle: marca les cantonades superior esquerra, superior dreta, inferior dreta i inferior esquerra.
3. Per al rectangle, indica amplada i fondària en la mateixa unitat (per exemple 6 × 3 metres). La perspectiva de la càmera, per si sola, no determina la proporció física real. S’admet una proporció entre 1:20 i 20:1.
4. Aplica la calibració i desa el projecte.

La previsualització adopta automàticament el contorn i la proporció calibrats; s’ha retirat el selector independent de formes. Les imatges i miniatures mantenen la proporció original amb bandes negres quan cal. Els textos i les notes es dibuixen separadament, sense estirar-los. Les zones rectangulars també poden utilitzar les cantonades del terra; l’editor segueix les dimensions calibrades.

Les calibracions antigues continuen sent circulars. En canviar la forma cal tornar a marcar els punts. Si un canvi a cercle deixa zones fora del terra, es rebutja la calibració i es conserven les dades actuals: cal adaptar les zones primer.

## Nou projecte

Abans de substituir el projecte actual, es pregunta si es vol desar:

- **Sí**: desa i continua només si el desament ha acabat correctament.
- **No**: continua sense desar el projecte actual.
- **Cancel·lar**: manté el projecte actual.

Cancel·lar el diàleg de fitxer, trobar errors de desament o tenir edicions pendents que impedeixin desar no crea el projecte nou. El primer inici des de la pantalla d’entrada no pregunta si es vol desar el projecte buit inicial.

## Mosaic només a la projecció

Les fotografies de zones simultànies es mostren juntes: dues meitats verticals, tres franges verticals o quatre quadrants. Amb més imatges, es crea una quadrícula automàtica. Cada imatge conserva la proporció; no es retalla ni s’estira.

Funciona amb targetes en zones diferents i amb zones superposades que permeten solapament. Les imatges de targetes també tenen una capa independent al mosaic i conserven els seus fades; els vídeos segueixen sense pista d’àudio integrada. Les regles visuals explícites mantenen la seva prioritat.

Les zones de presència desapareixen en confirmar-ne la sortida. Les zones amb temps després de sortir es mantenen durant el termini configurat. Quan no queda cap imatge simultània activa, es conserva el comportament anterior de la darrera fotografia persistent. La previsualització continua mostrant el mapa d’operació; el mosaic només es compon al projector.

## Validació

Proves automàtiques de geometria i serialització de la calibració, proporcions i clics del mapa, cancel·lació/desament abans de crear projecte, imatges simultànies en zones diferents o superposades, distribució del mosaic i conservació dels fitxers originals. També s’executa la suite de regressió.
Queda pendent la prova visual al Windows de l’usuari amb càmera i projector reals.
