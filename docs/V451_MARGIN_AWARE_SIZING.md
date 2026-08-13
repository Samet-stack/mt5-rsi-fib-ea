# V4.51 — dimensionnement plafonné par la marge

Date : 13 août 2026

Usage : Strategy Tester et compte démo uniquement

## Problème réellement observé

Sur XAUUSD M15, du 1er septembre au 1er décembre 2025, avec 3 000 USD,
un levier 1:100, un risque demandé de 2,7 % et un plafond de 25 % de la
marge libre, l'ancien moteur exigeait le volume exact correspondant au risque.
Si ce volume dépassait le plafond de marge, il rejetait tout le setup.

Le rapport brut contient une position perdante et -76,70 USD. Le journal est
plus précis que le premier diagnostic : sur 40 signaux acceptés, 35 setups ont
été rejetés par `REJECT_SIZE_MARGIN`. Il ne s'agissait donc pas d'une preuve
que le compte possède une limite universelle à 1 ou 1,5 % de risque ; le code
ne cherchait simplement jamais un volume inférieur.

## Correction

`InpRiskPercent` est maintenant interprété comme un **maximum**, et non comme
un volume obligatoire :

1. le moteur calcule d'abord le volume plafonné par le risque monétaire ;
2. il calcule 25 % de la marge libre disponible ;
3. si le volume demandé ne tient pas, une dichotomie cherche le plus grand
   nombre entier de pas `SYMBOL_VOLUME_STEP` dont la marge calculée par
   `OrderCalcMargin` reste sous la limite ;
4. le risque monétaire exact est recalculé sur ce volume final, coûts et
   slippage inclus ;
5. le setup est rejeté si même le volume minimum ne tient pas, si aucun calcul
   de marge valide n'est disponible, ou si le risque final dépasse le budget.

La marge n'est jamais supposée linéaire. Une erreur de calcul sur un gros
volume pousse la recherche vers des volumes plus petits, mais aucun volume
n'est accepté sans un résultat `OrderCalcMargin` valide. Le plafond de 25 %,
le levier 1:100 et tous les autres guards restent inchangés.

Chaque calcul écrit désormais une ligne structurée `SIZING_RESULT` contenant
le risque demandé, le volume demandé, la marge demandée, le volume final, le
risque réellement pris et la marge finale. Le dashboard distingue lui aussi
risque demandé et risque réalisé. Le funnel compte les réductions via
`SIZE_MARGIN_CAPPED` ; ce compteur n'est pas un rejet.

## Rejeu exact du cas 2,7 %

| Mesure | Ancien moteur | V4.51 |
| --- | ---: | ---: |
| Ticks réels | 100 % | 100 % |
| Positions | 1 | 17 |
| Gagnantes | 0 | 7 |
| Rejets de marge | 35 | 0 |
| Dimensionnements réduits | 0 | 30 |
| Net MT5 brut | -76,70 USD | +786,21 USD |
| Net après scénario 7 USD/lot | — | +764,30 USD |
| PF après scénario 7 USD/lot | — | 2,773 |
| Net stress 14 USD/lot | — | +742,39 USD |
| Drawdown equity maximal | 3,03 % | 7,63 % |

Sur les 33 ordres dimensionnés dans ce run, le risque calculé varie de 0,552 %
à 2,623 %, pour une moyenne de 1,523 %. Trois volumes tiennent sans réduction ;
les trente autres sont plafonnés par la marge. Ce test n'est donc pas une
simulation à risque constant de 2,7 %.

Le meilleur trade représente 23,1 % du profit brut ajusté. Le net reste à
+487,94 USD sans le meilleur et à +261,46 USD sans les deux meilleurs.

## Contrôle sur les quatre blocs de développement

Tous les rapports utilisent 100 % de ticks réels, 3 000 USD et 1:100.

| Bloc | Trades | Gagnants | Net ajusté 7 USD/lot | PF ajusté | DD equity max | Net stress 14 USD/lot |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| juillet–août 2025 | 9 | 1 | -144,43 | 0,464 | 10,45 % | -157,03 |
| septembre–novembre 2025 | 17 | 7 | +764,30 | 2,773 | 7,63 % | +742,39 |
| décembre 2025 | 4 | 1 | -37,58 | 0,722 | 4,43 % | -42,34 |
| février–avril 2026 | 16 | 7 | +796,55 | 2,155 | 9,17 % | +779,82 |
| **Somme diagnostique** | **46** | **16** | **+1 378,84** | **1,904** | — | **+1 322,84** |

La somme diagnostique redémarre à 3 000 USD sur chaque bloc et n'est pas une
courbe de portefeuille continue. Deux blocs sur quatre restent négatifs. Sur
87 dimensionnements, 71 sont plafonnés par la marge ; le risque calculé varie
de 0,496 % à 2,678 %, avec une moyenne de 1,570 %. Le meilleur trade représente
9,83 % du profit brut agrégé ; le net reste à +1 093,24 USD sans le meilleur et
à +816,88 USD sans les deux meilleurs.

Ces chiffres sont plus solides que le run isolé, mais toutes ces périodes ont
déjà servi au développement. Le résultat ne prouve ni la rentabilité future ni
la pertinence d'utiliser 2,7 % en démo. La hausse du risque amplifie aussi le
drawdown, qui atteint 10,45 % sur un bloc.

Le plafond de perte journalière existant réagit au PnL déjà réalisé et flottant ;
il ne remplace pas le budget de risque prospectif du premier trade de la journée.
Le stress à 2,7 % vérifie donc le moteur de marge, sans recommander ce niveau de
risque pour le compte démo.

## Archives

Les quatre rapports, leur source V4.51, le preset exécuté et l'EX5 sont gelés
avec SHA-256 dans `artifacts/experiments_v4_5/runs` :

- `09d87b5e-a4d2-40f7-9d85-09f92c1fe441` — juillet–août 2025 ;
- `c3ad7586-b36f-447d-aa63-c9ef876a60de` — septembre–novembre 2025 ;
- `127462a3-eb54-4e79-b82c-92d855e5de7f` — décembre 2025 ;
- `e288f310-c930-42ae-a4c4-796025d0ab2f` — février–avril 2026.

Le coût de 7 USD/lot reste une hypothèse et les manifests indiquent donc
`cost.verified=false`. Le preset public officiel reste volontairement à 0,25 %
et fermé par `InpCostModelVerified=false`. Le run à 2,7 % est un stress de
recherche archivé, pas le réglage conseillé pour un forward test.
