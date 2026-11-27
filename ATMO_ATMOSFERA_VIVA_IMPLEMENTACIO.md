# ATMO ESFERA FX · Atmosfera viva · Revisió 2

## Canvis
- Pantalla d'inici: imatges grans, adaptatives a l'amplada i alçada de les quatre targetes.
- Retall proporcional centrat (Pillow), amb qualitat Lanczos i redimensionament diferit 90 ms per evitar feina contínua en redimensionar la finestra.
- Les imatges també són clicables; els botons Entrar continuen funcionant.
- La finestra inicial proposa 1280 × 760 i conserva la maximització original i un mínim de 940 × 620.
- Es conserven els recursos visuals locals i la lògica de la integració 18.

## Proves
- Compilació Python de tot el projecte: correcta.
- Suite de proves amb pantalla virtual: iniciada, però no completada en el temps disponible; no s'afirma regressió completa.
- Cal verificar visualment a Windows i amb escalats 100%, 125% i 150%.
