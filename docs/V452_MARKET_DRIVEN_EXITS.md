# V4.52 — sorties dictées par le marché, pas par un RR imposé

Date de gel : 13 août 2026.

## Décision implémentée

La V4.52 sépare trois décisions qui étaient auparavant mélangées :

1. l'entrée reste le retracement limite Fibonacci de la stratégie ;
2. le stop vient de l'invalidation structurelle clôturée et la cible de la liquidité `P1` déjà observée ;
3. seulement après ces niveaux, l'EA mesure le RR net puis calcule le volume depuis le risque monétaire et la marge disponibles.

Le RR n'est donc jamais une consigne de TP en mode `EXIT_GEOMETRY_STRUCTURE`. Un seuil `InpMinNetRewardRisk` peut refuser une géométrie trop pauvre, sans jamais la transformer. Le profil Gold le laisse à zéro pour observer la distribution naturelle.

Le stop utilise l'extrême des `InpStructuralStopLookbackBars` dernières bougies clôturées, un buffer `InpStructuralStopBufferATR`, puis un plancher de distance `InpStructuralMinRiskATR`. Ce dernier a été ajouté après avoir détecté des stops de quelques ticks et des RR de 40 à 174 : ces chiffres étaient des artefacts de micro-distance, pas une preuve d'avantage.

## Candidat Gold retenu

Le preset public [`RSIFibEA_gold_m15_portfolio_research.set`](../presets/RSIFibEA_gold_m15_portfolio_research.set) utilise :

- XAUUSD M15, tendance H1 EMA200 sur bougie clôturée ;
- sortie RSI qualifiée : deux bougies consécutives en zone et reprise minimale de 4 points ;
- régime de volatilité `ATR(14) / ATR(100)` compris entre 0,80 et 2,20 ;
- entrée `-0,21`, stop ancre clôturée + `0,30 ATR`, distance minimale `0,25 ATR`, cible `P1` moins un tick ;
- aucun TP fixe en R, aucune prise partielle, aucun break-even, trailing ou time-exit dans cette expérience ;
- risque public 0,25 %, coût non validé et Gate 0 fermé.

Le preset de recherche archivé demandait 1 % de risque, gardait le plafond de marge à 25 % et utilisait 7 USD/lot pour exécuter le test. Cette valeur est une hypothèse de scénario, pas un barème broker vérifié ; les manifests l'enregistrent donc avec `verified=false`.

## Ablations de développement

Protocole commun : XAUUSD M15, dépôt 3 000 USD, levier 1:100, 100 % de ticks réels, quatre blocs de développement, coût normal 7 USD/lot et stress 14 USD/lot. Un seul facteur est modifié par ablation.

| Variante | Trades | Gagnants | Net normal | PF normal | Net sans meilleur |
| --- | ---: | ---: | ---: | ---: | ---: |
| Sorties structurelles seules | 57 | 13 | +171,77 | 1,146 | +0,07 |
| Pente EMA H1 | 57 | 13 | +171,77 | 1,146 | +0,07 |
| Divergence RSI obligatoire | 9 | 1 | −75,73 | 0,629 | −204,07 |
| Range minimum 1 ATR | 23 | 1 | −429,85 | 0,264 | −584,38 |
| Régime de volatilité | 49 | 12 | +291,98 | 1,289 | +120,28 |
| RSI H1 face à 50 | 3 | 0 | −64,65 | 0,000 | −49,47 |
| Qualité de sortie RSI | 22 | 8 | +489,08 | 2,313 | +317,38 |
| Qualité RSI + régime volatilité | 20 | 8 | **+537,09** | **2,655** | **+365,39** |

La combinaison finale était la seule combinaison testée : elle réunit les deux filtres qui avaient chacun amélioré le contrôle séparément. La pente EMA, la divergence, le range ATR et le RSI H1 sont rejetés pour ce candidat ; ils ne sont pas empilés après coup.

## Résultats par fenêtre du candidat

| Fenêtre | Trades | Gagnants | Net normal | Net stress | PF normal | Net sans meilleur |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2025-07-01 → 2025-09-01 | 3 | 0 | −72,29 | −76,07 | 0,000 | −72,29 |
| 2025-09-01 → 2025-12-01 | 8 | 5 | +437,30 | +431,07 | 5,763 | +265,60 |
| 2025-12-01 → 2026-01-01 | 4 | 2 | +155,41 | +151,84 | 3,792 | +15,84 |
| 2026-02-01 → 2026-05-01 | 5 | 1 | +16,67 | +13,87 | 1,159 | −104,66 |
| **Développement agrégé** | **20** | **8** | **+537,09** | **+520,71** | **2,655** | **+365,39** |

Le diagnostic post-sélection 2026-05-01 → 2026-08-01 donne 6 trades, 2 gagnants, +172,57 USD, PF 2,593 et +26,45 USD sans le meilleur trade ; sous stress : +167,04 USD et PF 2,489. Ce bloc n'est **pas** présenté comme hors échantillon : ses anciens logs avaient déjà servi à corriger le plancher du stop.

## Verdict

Le candidat est techniquement supérieur au contrôle sur ces données et respecte la demande de ne pas forcer le RR. Il ne démontre pas encore une rentabilité statistique : seulement 20 trades de développement, une fenêtre perdante et aucune fenêtre propre inutilisée après la correction de sécurité. Le Sharpe MT5 n'est pas utilisé dans ce verdict.

La suite correcte est un forward test démo gelé, sans retoucher les paramètres en fonction de ses pertes. Les critères avant toute nouvelle promotion sont : coût broker documenté, au moins 100 trades, résultat positif sous coûts stressés, PF supérieur à 1,20, drawdown acceptable, résultat non dépendant des deux meilleurs trades et stabilité sur plusieurs régimes.

## Archives reproductibles

Chaque dossier contient source, preset de recherche, EX5, rapport MT5, paramètres effectifs et hashes ; la comparaison est 111/111 pour les cinq runs :

- [`451d2568-bba8-4cde-b917-33274d4bb336`](../artifacts/experiments_v4_52/runs/451d2568-bba8-4cde-b917-33274d4bb336) — juillet–août 2025 ;
- [`f5b05006-87c2-4b72-9383-e795fe1d6e71`](../artifacts/experiments_v4_52/runs/f5b05006-87c2-4b72-9383-e795fe1d6e71) — septembre–novembre 2025 ;
- [`bd2cedc2-4011-4b03-8203-932cebc2e4a5`](../artifacts/experiments_v4_52/runs/bd2cedc2-4011-4b03-8203-932cebc2e4a5) — décembre 2025 ;
- [`1bdedc22-1021-43f1-9c66-b0571da5c65a`](../artifacts/experiments_v4_52/runs/1bdedc22-1021-43f1-9c66-b0571da5c65a) — février–avril 2026 ;
- [`1be2337c-27a8-4705-a7a9-b1ec458498b2`](../artifacts/experiments_v4_52/runs/1be2337c-27a8-4705-a7a9-b1ec458498b2) — diagnostic post-sélection mai–juillet 2026.
