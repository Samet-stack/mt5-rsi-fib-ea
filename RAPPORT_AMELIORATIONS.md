# Journal technique V4.30 — état de validation

Ce document décrit les fonctionnalités présentes dans le code. Il ne constitue
ni une promesse de rendement, ni un conseil financier, ni la validation d’une
espérance positive.

## État vérifiable

- L’EA reste limité au Strategy Tester ou à un compte MT5 classé démo.
- Les presets publics conservent `InpCostModelVerified=false` : ils refusent de
  démarrer tant que le coût aller-retour du broker n’a pas été documenté.
- Les 146 tests Python vérifient la géométrie, le sizing, les gardes broker,
  les restaurations, le parseur, les coûts et les registres expérimentaux.
- La compilation native MetaEditor build 6090 affiche `0 errors, 0 warnings`
  pour la V4.30 archivée.

## Fonctionnalités implémentées

La branche V4.30 contient, en plus de la logique RSI/Fibonacci de base, des
modules optionnels désactivables :

1. géométrie SL/TP adaptative à l’ATR ;
2. trailing stop Fibonacci ;
3. sortie de stagnation et protection de fin de semaine ;
4. structure de marché et buffer de liquidité ;
5. divergence RSI ;
6. calendrier explicite désactivé/live/fichier testeur, fail-closed ;
7. prise de profit partielle vérifiée contre le lot minimum et les retcodes ;
8. funnel de premiers rejets et diagnostic exact du capital minimum ;
9. outils d'ajustement de coûts et d'archivage sans écrasement.

La présence d’un module dans le code prouve seulement son implémentation. Elle
ne prouve pas son utilité économique.

## Matrice des preuves

| Famille | Artefacts publics | Statut raisonnable |
| --- | --- | --- |
| Baseline/V2/V3 enregistrée | rapports, sonde, diagnostics et ledger hashé | candidat historique rejeté ou techniquement invalide après audit des coûts |
| V3.4/V3.5 | quelques rapports MT5 historiques | exploratoire, non assimilable à un holdout vierge |
| V4.0/V4.2 | aucun rapport brut correspondant archivé dans le dépôt | performance non vérifiée ; aucun chiffre revendiqué |
| V4.30 janvier 2026 | sept rapports vrais ticks, presets effectifs, EX5, funnels et manifests hashés | +20,09 USD ajustés sur le meilleur run, mais seulement 10 positions : inconclusif |

Les anciennes appellations de fichiers comme `supreme`, `annihilator` ou
`target600` sont conservées uniquement pour ne pas casser la traçabilité des
expériences. Elles ne décrivent pas un niveau de performance attendu.

## Pourquoi les anciens tableaux marketing ont été retirés

Des chiffres V4.0/V4.2 précis avaient été inscrits sans rapport brut public
correspondant. Ils ne sont donc pas reproductibles. Une mesure ne réintègre la
documentation que si le dépôt contient au minimum : source et preset hashés,
rapport MT5 brut, symbole/serveur/période, vrais ticks, coûts, nombre total
d’essais et diagnostic enregistré.

La V4.30 réintroduit uniquement les mesures appuyées par les archives de
[`artifacts/experiments_v4/runs`](artifacts/experiments_v4/runs). Le détail,
les coûts et les limites statistiques figurent dans
[`docs/JAN_2026_V430_ABLATION.md`](docs/JAN_2026_V430_ABLATION.md). Janvier
2026 a servi à choisir entre les sorties et ne constitue plus un holdout.

## Prochaines étapes

1. choisir définitivement le marché cible et le symbole broker exact ;
2. documenter commission, spread, swap, slippage et marge ;
3. enregistrer chaque hypothèse avant son test ;
4. tester une seule modification par ablation ;
5. conserver un holdout temporel réellement vierge ;
6. n’envisager un forward qu’en démo et après réussite de tous les gates.

Les contributions doivent suivre [CONTRIBUTING.md](CONTRIBUTING.md) et le
protocole de [docs/BACKTEST_PROTOCOL.md](docs/BACKTEST_PROTOCOL.md).
