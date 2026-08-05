# Diagnostic de la baseline V3

Conclusion : **le candidat `StopRatio=-0.39`, break-even activé, est rejeté**. Le rapport mai–juin perd déjà de l'argent avant ajout d'une commission réaliste. Les deux fenêtres sont en plus techniquement invalides comme preuve de rentabilité à cause des coûts non vérifiés et du champ `fee` absent.

## Résultats reproduits

| Mesure | IS fév.–avr. | Mai–juin exposé |
|---|---:|---:|
| Trades | 52 | 48 |
| PnL positif / nul / négatif | 8 / 1 / 43 | 2 / 3 / 43 |
| TP complets | 3 | 1 |
| Net | +55,30 USD | **-21,87 USD** |
| Profit factor | 1,71 | **0,67** |
| Plus gros gain | 62,72 USD | 44,26 USD |
| Part du plus gros gain dans le brut positif | 47,11 % | **99,95 %** |
| Net sans le plus gros gain | -7,42 USD | **-66,13 USD** |
| Wilson 95 % du taux de TP | 1,98–15,64 % | 0,37–10,90 % |
| Taux de TP d'équilibre normalisé en R | 3,67 % | 4,26 % |
| Bootstrap bloc 5 du R journalier moyen | -0,347 à +1,005 | -0,628 à +0,306 |
| Durée médiane | 79,5 s | 71,5 s |
| Sorties sous 5 minutes | 37/52 | 37/48 |

La reconstruction du net correspond au rapport à l'arrondi flottant près. Le calcul de risque en R utilise la valeur issue de `OrderCalcProfit` de la sonde. MT5 range les trades exactement nuls parmi les « profit trades » ; le diagnostic exporte séparément positifs, nuls et négatifs pour éviter cette ambiguïté.

## Interprétation causale

- La cible complète est un événement rare : trois TP en IS et un seul ensuite.
- Le résultat est de type jackpot. Sans le meilleur trade, les deux périodes sont négatives.
- 71 à 77 % des sorties arrivent en moins de cinq minutes alors que le signal est M15. Le stop semble souvent vivre dans le bruit microstructurel immédiat.
- En IS, la branche long perd 13,11 USD tandis que le résultat positif vient de la branche short. En mai–juin, les shorts perdent 22,37 USD.
- Le taux de TP observé n'a pas de borne inférieure crédible au-dessus du seuil d'équilibre en R.
- Le bootstrap journalier recouvre largement zéro sur les deux fenêtres.
- La commission est nulle dans le rapport et les frais de deal ne sont pas exportés. Le résultat net réel du broker cible ne peut donc qu'être moins certain, et probablement moins bon.

Le Fibonacci n'est pas validé comme source d'edge. Une étude empirique de retracements peut motiver une hypothèse, mais ne remplace pas une validation propre sur l'instrument exact : [Chong et Ng, 2021](https://doi.org/10.1016/j.eswa.2021.115893).

## Ce que les rapports ne permettent pas de savoir

- MFE et MAE par setup ;
- passage de prix avant fill, position dans la file et non-fills conservateurs ;
- spread exact à l'entrée et au stop ;
- décomposition commission/frais/exchange sur le broker final ;
- comportement proche d'une échéance MGC ;
- performance sur un holdout réellement vierge.

## Verdicts séparés

- Validité technique/coûts : `INVALID`.
- Évaluation économique IS : `INCONCLUSIVE`, très concentrée.
- Évaluation économique mai–juin : `REJECTED`.
- Autorisation de passer à l'optimisation : `NON`.

Les diagnostics machine sont archivés sous les runs `98c7d463-751b-41a4-8869-cb75a26a003e` et `83ebdfe1-7f5e-43b0-af2e-47abed4deeb3`.
