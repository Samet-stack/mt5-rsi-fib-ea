# V4.50 — ablation macro et géométrie Gold

Date : 13 août 2026

Capital testeur : 3 000 USD

Risque : 0,25 % de l'equity par setup

Levier : 1:100

Instrument : XAUUSD, M15, tendance H1

Usage : Strategy Tester et compte démo uniquement

## Verdict direct

Le filtre EMA200 H1 est utile, mais il n'est pas un filtre « pare-balles » et
ne suffit pas à rendre la stratégie rentable. Le changement le plus robuste de
cette itération est la combinaison suivante :

- achats et ventes autorisés ;
- chaque sens doit être aligné avec le close H1 face à l'EMA200 H1 ;
- revalidation de cet alignement avant le placement, pendant la vie du pending
  et immédiatement avant l'envoi au broker ;
- stop Fib fixe à `-0.50` et objectif fixé à 3R ;
- aucun trailing, break-even, partiel ou filtre RSI H1 dans ce candidat ;
- risque maintenu à 0,25 %, sans utiliser le levier comme source de performance.

Sur quatre blocs de développement totalisant neuf mois calendaires, ce candidat
produit 43 positions, 15 gagnantes, +121,18 USD après un scénario de coût de
7 USD/lot et un profit factor ajusté de 1,737. Le meilleur trade représente
8,0 % du profit brut ; le net reste à +98,22 USD sans le meilleur trade et à
+76,41 USD sans les deux meilleurs.

Ce résultat est prometteur, mais il ne valide pas la rentabilité future : les
fenêtres ont servi à choisir la règle, le coût broker n'est pas vérifié, une des
quatre périodes perd de l'argent et 43 trades restent un petit échantillon. Le
profil public est donc un **candidat de recherche**, fermé par
`InpCostModelVerified=false`.

## Correction de l'affirmation initiale

Le rapport présenté comme « +997,54 USD, PF 2,34 » contient réellement 14
positions, dont trois gagnantes, avec 2 % de risque et un levier 1:500 sur la
fenêtre septembre–novembre 2025. Après le scénario de 7 USD/lot, son net est
+969,47 USD et son PF 2,263, mais les deux meilleurs trades représentent 70,8 %
du profit brut. Sans ces deux trades, le net devient -260,10 USD.

Le levier 1:500 ne crée pas l'avantage statistique. À risque proportionnel, il
change surtout la marge disponible ; le passage de 0,25 % à 2 % amplifie les
gains et les pertes. Ce rapport est donc un indice de recherche, pas une preuve
que le bot est une « imprimante à billets ».

## Données et méthode

Tous les essais retenus utilisent MetaTrader 5 build 6090, le serveur
MetaQuotes-Demo et le modèle « Every tick based on real ticks ». Chacun des
quatre rapports affiche 100 % de ticks réels :

| Bloc | Positions | Gagnants | Net brut | DD equity max | Net après 7 USD/lot | PF ajusté | Net stress 14 USD/lot |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2025-07-01 → 2025-09-01 | 9 | 1 | -30,24 | 2,11 % | -33,32 | 0,360 | -36,40 |
| 2025-09-01 → 2025-12-01 | 17 | 7 | +68,49 | 1,35 % | +64,85 | 2,022 | +61,21 |
| 2025-12-01 → 2026-01-01 | 6 | 3 | +42,24 | 0,45 % | +40,98 | 3,259 | +39,72 |
| 2026-02-01 → 2026-05-01 | 11 | 4 | +49,79 | 0,68 % | +48,67 | 2,583 | +47,55 |
| **Somme diagnostique** | **43** | **15** | **+130,28** | — | **+121,18** | **1,737** | **+112,08** |

La somme n'est pas une courbe de portefeuille continue : chaque bloc redémarre
avec 3 000 USD. Le PF agrégé est recalculé à partir de 285,58 USD de gains bruts
ajustés et -164,40 USD de pertes brutes ajustées. Le stress utilise 14 USD/lot
et donne un PF de 1,656. Le spread reste déjà implicite dans les exécutions MT5
et n'est jamais facturé une seconde fois.

Les rapports bruts, le source, le preset exécuté et l'EX5 sont archivés avec
SHA-256 dans `artifacts/experiments_v4_5/runs` :

| Bloc | Run immuable |
| --- | --- |
| juillet–août 2025 | `6db19cc6-3f23-4cb8-9ef8-3a4617482801` |
| septembre–novembre 2025 | `f750116f-3214-4d30-8e5b-c6f7923d5db2` |
| décembre 2025 | `25bb06b4-0f1c-47d9-ae84-8e520e546fe3` |
| février–avril 2026 | `ef391c9f-0055-4346-80bf-4ed4551f49da` |

Les manifests indiquent volontairement `cost.verified=false`. Les paramètres
sont lisibles dans chaque rapport MT5 ; la comparaison JSON automatique n'a
pas été exécutée pour ces quatre archives et les manifests l'indiquent aussi.

## Ablations

### 1. Cible historique très éloignée

La référence deux sens, sans MTF et avec la géométrie proche de 9,55R, produit
191 positions et seulement 15 gagnantes sur les mêmes blocs : -297,43 USD
ajustés et PF 0,728. Le long-only et l'EMA200 améliorent septembre–novembre,
mais échouent dans les blocs voisins. L'idée « conserver trois home runs et
supprimer les pertes » n'est donc pas stable hors de la fenêtre choisie.

### 2. Grille de TP, long-only avec EMA200 H1

| Objectif | Positions | Win rate | Net ajusté | PF ajusté | Blocs positifs | Net stress |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2R | 19 | 21,1 % | -30,90 | 0,633 | 0/4 | -34,54 |
| 3R | 34 | 29,4 % | +54,55 | 1,403 | 3/4 | +48,18 |
| 4R | 40 | 25,0 % | +77,81 | 1,447 | 2/4 | +70,04 |

Le 4R maximise le net de cette petite grille, mais le 3R gagne sur trois blocs
sur quatre, obtient un meilleur win rate et reste positif sans ses deux
meilleurs trades. Le 3R est retenu pour la stabilité, pas pour maximiser le
backtest.

### 3. Filtres macro supplémentaires

- La pente EMA optionnelle ne change aucun des trades observés. Elle reste dans
  le moteur pour de futures hypothèses, mais est désactivée dans le candidat.
- Ajouter un RSI H1 autour de 50 réduit l'échantillon à deux trades, tous deux
  perdants. Cette variante est rejetée.
- Autoriser les ventes seulement lorsqu'elles sont sous l'EMA200 H1 ajoute neuf
  trades, dont cinq gagnants. Sur les blocs testés, cette composante apporte
  +67,93 USD ajustés avec un PF de 3,44, mais elle n'est positive que sur deux
  blocs et reste trop petite pour être validée seule.

Dans le candidat symétrique, la décomposition donne 34 achats, 10 gagnants,
+53,25 USD et PF 1,39 ; puis 9 ventes, 5 gagnantes, +67,93 USD et PF 3,44. Cette
symétrie évite de supposer que l'Or doit toujours être acheté.

## Changements du moteur V4.50

- `InpTradeDirection` autorise les deux sens, long-only ou short-only. Un signal
  bloqué reçoit un motif de funnel explicite au lieu de disparaître des mesures.
- Le filtre MTF utilise exclusivement le close et l'EMA de la bougie H1 fermée.
- Une pente EMA directionnelle optionnelle utilise deux valeurs fermées, un
  lookback paramétrable et un seuil en pourcentage symétrique.
- La politique directionnelle et le filtre MTF sont contrôlés au signal, avant
  le placement, pendant l'attente et juste avant l'ordre. Une invalidation macro
  annule le pending et possède son propre compteur de funnel.
- Le runner PowerShell refuse désormais un rapport dont la qualité réelle est
  absente ou inférieure à 99 %. Un essai 2024 affichant 0 % de ticks réels a été
  rejeté et n'entre dans aucun résultat ci-dessus.

## Étape suivante obligatoire

Le candidat doit maintenant être gelé. Il ne faut plus modifier ses paramètres
en regardant les mêmes blocs. La prochaine preuve doit venir de nouvelles
données réelles-ticks chronologiquement ultérieures ou d'un nouveau flux broker,
puis d'un walk-forward et d'un forward test démo. Les gates minimaux restent :

1. coût exact du compte démo documenté par symbole ;
2. au moins 100 trades cumulés pour une première lecture moins fragile ;
3. PF normal ≥ 1,20 et PF stress ≥ 1,00 ;
4. net positif sans le meilleur trade et sans les deux meilleurs ;
5. drawdown compatible avec les limites et aucune période structurellement
   dépendante d'une seule direction ;
6. aucune hausse du risque pour sauver un edge négatif.

Même le passage de ces gates ne garantirait pas une rentabilité future.
