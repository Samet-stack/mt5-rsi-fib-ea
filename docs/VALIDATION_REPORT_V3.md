# Rapport de validation V3

## VERDICT FINAL : REJETÉ

Ce verdict vise le candidat historique RSI/Fibonacci `XAUUSD M15`, entrée -0,21, stop -0,39 et break-even à P0. Il n'autorise ni optimisation supplémentaire sur les mêmes fenêtres, ni forward, ni activation d'Algo Trading.

## Faits

- IS déjà contaminé : 52 trades, +55,30 USD, PF 1,71, trois TP complets ; sans le meilleur gain, -7,42 USD.
- Validation temporelle déjà exposée : 48 trades, -21,87 USD, PF 0,67, un TP complet ; sans le meilleur gain, -66,13 USD.
- Les deux intervalles bootstrap du R journalier recouvrent zéro.
- Commission à zéro et colonne `fee` absente ; coûts du broker cible inconnus.
- Les captures montrent MGCQ2026, mais seule une sonde du CFD `XAUUSD` de `MetaQuotes-Demo` est disponible ; la présence de MGC chez le broker n'est pas établie.
- Le Gate 0 est bloqué et les presets V3 échouent volontairement avec `InpCostModelVerified=false`.
- 111 tests passent ; l'EA V3 compile avec zéro erreur et zéro avertissement. Cette qualité logicielle ne transforme pas une preuve économique négative en edge.

## Inférences prudentes

- L'espérance positive n'est pas démontrée et la distribution est trop concentrée pour soutenir une revendication de robustesse.
- Des coûts réalistes ne résolvent pas le résultat négatif mai–juin ; ils le dégradent ou laissent au mieux davantage d'incertitude.
- Le taux très élevé de sorties sous cinq minutes justifie un diagnostic MFE/MAE et microstructure, pas un nouvel élargissement opportuniste du stop.

## Décision opérationnelle

- Aucun ordre réel ni forward automatique.
- Aucun nouveau choix de ratio à partir des données déjà ouvertes.
- Reprise possible uniquement comme nouveau programme de recherche après choix du marché exact, barème broker, nouvelle sonde, ledger shadow et plan de puissance préenregistré.

Les preuves machine se trouvent dans [artifacts/experiments_v3](../artifacts/experiments_v3), et les limites détaillées dans [BASELINE_DIAGNOSTIC_V3.md](BASELINE_DIAGNOSTIC_V3.md).
