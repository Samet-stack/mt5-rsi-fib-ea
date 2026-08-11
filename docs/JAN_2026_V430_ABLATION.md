# Ablation V4.30 — XAUUSD M15, janvier 2026

## Verdict

La V4.30 reproduit le meilleur résultat technique observé sur cette fenêtre :
`+20,79 USD` natifs et `+20,09 USD` après l'hypothèse de coût de
`7 USD/lot`. Ce résultat est **inconclusif**, pas une preuve de rentabilité :
il ne contient que 10 positions, quatre gains strictement positifs après coût,
et un seul long représente 73,3 % du bénéfice net ajusté.

Cette fenêtre a servi au diagnostic et est désormais contaminée pour toute
sélection future. Elle ne doit jamais être présentée comme hors échantillon.

## Environnement figé

- serveur : MetaQuotes-Demo, build 6090 ;
- instrument : XAUUSD, M15 ;
- fenêtre : `2026-01-01` inclus à `2026-02-01` exclu ;
- dépôt : 3 000 USD, levier 1:100 ;
- modèle : chaque tick basé sur des ticks réels ;
- qualité : 100 %, 18 446 803 ticks, 1 922 barres ;
- source SHA-256 : `dc57042cfb3a46e81a3f3b9b64b696210a14631d4c4de3455615b98c745103f6` ;
- EX5 SHA-256 : `32458252edf489d6d220dc07c5c67c4227c4d1819e1c237430cd11a6c2696b5b` ;
- compilation MetaEditor : 0 erreur, 0 avertissement.

Le spread est déjà contenu dans les prix d'exécution du testeur. L'analyse ne
le soustrait donc pas une seconde fois. Le scénario normal ajoute seulement le
complément de commission/frais nécessaire pour atteindre `7 USD/lot`
aller-retour ; le stress utilise `14 USD/lot`.

## Résultats des sorties

La référence active trailing Fibonacci et stagnation, désactive les filtres
stricts et la prise partielle, et emploie 0,50 % uniquement dans le testeur.
Toutes les positions exécutées restent à 0,01 lot : le passage de 0,25 à
0,50 % franchit le minimum broker, il ne double pas le volume.

| Variante | Changement | Positions | Net MT5 | Net coût 7 | Net coût 14 | PF coût 7 | Sharpe | DD equity |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Référence | trailing ON, stagnation ON | 10 | +20,79 | +20,09 | +19,39 | 1,689 | 1,61 | 1,22 % |
| Trailing OFF | un paramètre | 10 | -29,00 | -29,70 | -30,40 | 0,000 | -1,38 | 2,24 % |
| Stagnation OFF | un paramètre | 10 | +13,53 | +12,83 | +12,13 | 1,352 | 0,90 | 1,27 % |
| Sorties simples | trailing OFF + stagnation OFF | 10 | -36,26 | -36,96 | -37,66 | 0,000 | -1,56 | 2,49 % |
| Risque 0,25 % | référence, risque réduit | 0 | 0,00 | 0,00 | 0,00 | N/A | 0,00 | 0,00 % |
| Partial ON | référence + prise partielle | 0 | 0,00 | 0,00 | 0,00 | N/A | 0,00 | 0,00 % |
| Filtres stricts | qualité RSI + vrai BOS | 1 | -0,06 | -0,13 | -0,20 | 0,000 | -0,01 | 0,50 % |

Le trailing explique l'essentiel du résultat observé sur janvier, mais dix
positions ne suffisent pas pour conclure qu'il possède un avantage stable.
Aucun trade de la référence n'a atteint le TP final à 5,5R.

## Funnel explicite

La V4.30 journalise un seul premier motif de rejet par croisement RSI.

| Variante | Croisements RSI | Rejet qualité | Rejet BOS | Signaux acceptés | Rejet lot min | Rejet partial indivisible | Ordres placés |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Référence | 50 | 0 | 0 | 38 | 27 | 0 | 11 |
| Risque 0,25 % | 55 | 0 | 0 | 46 | 46 | 0 | 0 |
| Partial ON | 55 | 0 | 0 | 46 | 30 | 16 | 0 |
| Filtres stricts | 55 | 32 | 21 | 2 | 1 | 0 | 1 |

À 0,25 %, le budget est de 7,50 USD. Les 46 setups acceptés auraient exigé,
au lot minimal de 0,01, entre 8,95 et 150,14 USD de risque défavorable. Le
capital requis pour respecter exactement 0,25 % allait donc de 3 580 à
60 056 USD. L'EA refuse ces trades au lieu de forcer le lot minimal.

Une division 50/50 de 0,01 lot produit 0,005 lot, inférieur au minimum et au
pas de 0,01. La V4.30 rejette explicitement les 16 setups qui étaient autrement
dimensionnables. Elle ne marque plus silencieusement une prise partielle comme
réalisée.

## Concentration et incertitude

Sur la référence après coût normal :

- net : +20,09 USD (+0,67 % du dépôt) ;
- quatre positions positives et six négatives après coût ;
- meilleure position : +14,72 USD, soit 73,3 % du net ;
- net sans la meilleure position : +5,37 USD ;
- net sans les deux meilleures : -7,95 USD ;
- moyenne : +2,01 USD/position, médiane : -0,10 USD ;
- intervalle Student 95 % de la moyenne : environ `[-4,99 ; +9,01]` USD.

Le Sharpe MT5 de 1,61 et le PF de 1,72 ne compensent pas cet échantillon trop
petit et concentré. Le score `OnTester` reste correctement à `-1` parce que le
plancher configuré de 15 positions n'est pas atteint.

## Calendrier reproductible

Trois modes sont maintenant distincts :

- `0` — désactivé, aucun appel calendrier ;
- `1` — calendrier live, interdit dans Strategy Tester ;
- `2` — fichier versionné dans `Terminal/Common/Files`.

Les tests MT5 ont confirmé : mode live dans le testeur → initialisation refusée ;
fichier absent → initialisation refusée ; fichier synthétique valide → une
seule entrée bloquée dans la fenêtre exacte. L'événement synthétique a retiré
le meilleur trade et ramené le net natif de +20,79 à +6,00 USD. Ce test valide
le mécanisme, pas une règle économique ni des données d'actualité.

Le schéma CSV attendu est documenté dans
[`NEWS_TESTER_FILE.md`](NEWS_TESTER_FILE.md).

## Archives immuables

Chaque dossier contient le source, le preset effectif, l'EX5, le rapport MT5,
le résumé du funnel, les paramètres relus depuis le rapport et un manifeste de
hashes. La comparaison preset/rapport porte sur 91 paramètres et réussit pour
les sept runs.

| Variante | Run ID | SHA rapport (12) |
| --- | --- | --- |
| Référence | `66c61cdf-355d-4518-9a1d-cccd0a208c46` | `398675719575` |
| Trailing OFF | `7393add0-59db-459d-8446-b1bfd72dde14` | `9881f1d947c7` |
| Stagnation OFF | `274a081d-2adc-427f-8d04-644d6a66342f` | `bf2e1471f8ff` |
| Sorties simples | `fd9be504-4cc9-4c04-9881-40bdeb24628d` | `66be31b56f3c` |
| Risque 0,25 % | `d5f412f5-6a64-4703-9395-10459372b0bb` | `0369945f9112` |
| Partial ON | `3d198a7e-2c9e-4b8c-a22e-245c2124ac43` | `13c83de81239` |
| Filtres stricts | `5b233e6e-6319-4037-9763-cbbcc3edc891` | `fc0a3c4f6900` |

## Décision suivante

La référence trailing + stagnation est seulement le meilleur candidat de ce
diagnostic. Elle doit être gelée puis évaluée sur des fenêtres non utilisées
pour sa sélection, avec coûts normal/stress, correction des essais multiples
et bloc-bootstrap. Une validation forward démo exige au minimum 150 positions,
une période d'au moins douze mois, une borne basse d'espérance nette en R
positive, un PF ajusté supérieur à 1 sous stress et un résultat qui reste
positif sans le meilleur trade.

Jusqu'à satisfaction de ces critères : **recherche/testeur et démo uniquement,
performance non validée, aucune promesse de gain**.
