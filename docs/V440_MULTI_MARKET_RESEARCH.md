# V4.40 — recherche multi-marchés Gold, Nasdaq et EURUSD

Date : 11 août 2026

Capital testeur : 3 000 USD

Levier : 1:100

Usage : Strategy Tester et compte démo uniquement

## Verdict direct

La V4.40 améliore le moteur et la qualité des mesures, mais **ne démontre pas
encore une stratégie rentable**. Le problème de fréquence a été levé sur le
couple Gold + Nasdaq : 19 positions sur la fenêtre de 32 jours, soit 17,81
positions par 30 jours. En revanche, le gate de robustesse échoue après le
scénario de coûts de développement. Augmenter le risque ou ouvrir davantage de
trades ne corrigerait pas ce défaut statistique.

La fenêtre juillet 2026 a servi à choisir et modifier les règles. Elle est donc
contaminée et ne pourra jamais servir de validation hors échantillon.

## Changements du moteur

- Le volume est recalculé pour chaque trade à partir de l'equity, du stop réel,
  des propriétés du symbole, du slippage, des coûts et de la marge. Aucun volume
  fixe commun aux marchés n'est imposé.
- Le break-even cherche par `OrderCalcProfit` le prix couvrant le coût
  aller-retour en devise du compte avant d'ajouter l'offset demandé.
- Le nouveau trailing R utilise la distance entrée→stop initiale et immuable.
  Cette géométrie est reconstruite depuis l'historique après redémarrage.
- Les limites portefeuille comptent, sur tous les symboles d'une plage de magic
  numbers, les positions, les ordres, les entrées du jour et le PnL journalier
  réalisé + flottant.
- Les sorties vendredi et stagnation vérifient désormais propriété, contexte
  démo/testeur et retcode broker ; un refus est journalisé puis retenté.
- Le funnel possède un motif explicite `REJECT_PORTFOLIO`.

## Symboles et profils

La sonde testeur sans ordre a confirmé que le Nasdaq du serveur
`MetaQuotes-Demo` est exposé sous le symbole `USTEC`. Les profils publics sont :

- `RSIFibEA_gold_m15_portfolio_research.set` ;
- `RSIFibEA_nasdaq_m15_portfolio_research.set` ;
- `RSIFibEA_eurusd_m15_portfolio_research.set`.

Ils utilisent des magic numbers distincts dans une plage partagée et restent
fermés par `InpCostModelVerified=false`. Ils ne doivent pas être activés tant
que le coût exact de chaque symbole n'a pas été documenté.

## Essais de développement de juillet 2026

Tous les runs ci-dessous utilisent M15 et le mode « every tick based on real
ticks ». Les chiffres bruts proviennent des rapports MT5. Le montant de 7 USD
par lot a été utilisé uniquement comme scénario technique uniforme ; il n'est
pas considéré comme un barème validé pour `USTEC`.

| Composant | Positions | Net brut | PF brut | Net avec scénario 7 USD/lot | Décision |
| --- | ---: | ---: | ---: | ---: | --- |
| XAUUSD, candidat C | 6 | -1,39 USD | 0,94 | -2,79 USD | rejeté |
| USTEC, candidat C | 13 | +8,04 USD | 1,35 | -33,96 USD | rejeté, coûts non vérifiés et résultat concentré |
| EURUSD, candidat B | 26 | -45,53 USD | 0,51 | non retenu | rejeté avant nouvelle itération |

L'agrégation des composants XAUUSD + USTEC donne, sous ce même scénario :

- 19 positions et 17,81 positions par 30 jours ;
- net ajusté : -36,75 USD ;
- profit factor ajusté : 0,518 ;
- net sans le meilleur trade : -54,81 USD ;
- meilleur trade : 45,69 % du profit brut ;
- seul le critère de fréquence passe ; tous les critères d'edge et de
  concentration échouent.

Cette somme n'est pas une courbe de portefeuille synchronisée : MT5 a testé
chaque symbole séparément. Elle ne valide donc pas les interactions simultanées
des limites portefeuille.

## Pourquoi davantage de trades ne suffit pas

Le test EURUSD permissif produit 26 positions, mais perd 45,53 USD avec un PF
de 0,51. Cela montre que le blocage principal n'est plus seulement la rareté
des signaux : le signal doit avoir un avantage après coûts et ne pas dépendre
d'un seul gros gagnant. Le risque par trade restera à 0,25 % pendant la phase
de recherche ; le relever masquerait l'absence d'edge sans la résoudre.

## Gate suivant

Une configuration ne devient candidate que si elle respecte un protocole
pré-déclaré :

1. documenter séparément commission/frais et stress de slippage de XAUUSD,
   `USTEC` et EURUSD sur le compte démo ciblé ;
2. geler les règles et les plages de paramètres avant de choisir de nouvelles
   fenêtres ;
3. séparer chronologiquement entraînement, validation et test final ; janvier
   et juillet 2026 sont interdits comme test final ;
4. exiger au moins 99 % de ticks réels et des fenêtres strictement identiques ;
5. rejeter si le PF normal est inférieur à 1,20, le PF stress inférieur à
   1,00, le net sans meilleur trade négatif, un composant négatif ou le meilleur
   trade supérieur à 35 % du profit brut ;
6. limiter la fréquence cible à 10–80 positions par 30 jours pour éviter à la
   fois l'échantillon minuscule et l'overtrading ;
7. confirmer ensuite par walk-forward, test final untouched et forward démo.

Le script `tools/portfolio_evaluator.py` automatise les contrôles 4 à 6 avec un
coût explicitement fourni pour chaque symbole. Ce gate sert à rejeter les
mauvaises hypothèses ; son passage ne garantirait toujours pas une rentabilité
future.
