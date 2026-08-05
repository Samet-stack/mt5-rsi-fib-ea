# Résultats de validation MT5 — 4 août 2026

## Décision

Le moteur est techniquement exploitable en test, mais **aucun preset n'est validé pour le trading automatique**, même sur compte démo. Le candidat sélectionné en in-sample a échoué sur la fenêtre hors échantillon ; il est donc rejeté et ne doit pas être activé.

Cette décision ne constitue ni un conseil financier ni une promesse de rentabilité.

## Environnement vérifié

- MetaTrader 5 / MetaEditor build 6090, binaires MetaQuotes signés ;
- compte et testeur configurés à 3 000 USD, levier 1:100 ;
- EA compilé nativement en X64 avec `0 errors, 0 warnings` ;
- source déployée identique au projet, SHA-256 `D546A16463521BA2963D797F162602C0CAEF285ABA77109BE8F3B903A7088A93` ;
- 71 tests Python réussis ;
- tests MT5 exécutés avec `Model=4`, agents locaux uniquement et rapports indiquant `100% ticks réel`, sauf les essais 2025 explicitement rejetés ci-dessous.

## Smokes techniques — juillet 2026

Ces runs vérifient le chargement, les niveaux, les ordres, les protections et la fin d'exécution. Ils ne forment pas une validation statistique.

| Symbole / preset | Trades | Gagnants | Net USD | PF | DD equity max |
|---|---:|---:|---:|---:|---:|
| EURUSD baseline 0,25 % | 23 | 0 | -168,34 | 0,00 | 6,49 % |
| EURUSD V2 0,10 % | 2 | 0 | -5,58 | 0,00 | 0,96 % |
| XAUUSD baseline 0,25 % | 12 | 0 | -77,67 | 0,00 | 2,59 % |
| XAUUSD V2 0,10 % | 2 | 0 | -2,68 | 0,00 | 2,42 % |

Le code applique correctement `Entry=-0,21`, `SL=-0,29` et `TP=2,56`. La faiblesse observée est structurelle : la distance entrée→stop ne vaut que `0,08 × range`, contre `2,77 × range` jusqu'à la cible, soit un ratio nominal proche de 34,6:1. Le stop se retrouve fréquemment dans le bruit et le spread.

## Contrôle étendu gelé — février à juin 2026

| Preset existant | Trades | Gagnants | Net USD | PF | DD equity max | Décision |
|---|---:|---:|---:|---:|---:|---|
| Baseline 0,25 % | 114 | 3 | -134,45 | 0,82 | 13,41 % | Rejeté |
| V2 0,10 % | 5 | 1 | -9,02 | 0,05 | 0,53 % | Rejeté, échantillon trop faible |

## Ablation parcimonieuse sur XAUUSD M15

Fenêtre de recherche : `2026-02-01 → 2026-05-01`. Tous les runs utilisent les mêmes ticks réels et un risque de 0,10 %. L'entrée `-0,21` et la cible `2,56` restent inchangées.

| Variante | Trades | Gagnants | Net USD | PF | DD equity max | OnTester |
|---|---:|---:|---:|---:|---:|---:|
| Contrôle, SL -0,29 | 70 | 3 | +39,01 | 1,25 | 3,46 % | 3,3415 |
| SL -0,39 | 52 | 4 | +58,58 | 1,51 | 2,39 % | 3,4201 |
| SL -0,39 + BE à P0 | 52 | 9 | +55,30 | 1,71 | 1,94 % | 3,7653 |
| SL -0,49 | 25 | 2 | -12,62 | 0,76 | 1,20 % | -1 |
| SL -0,49 + BE à P0 | 25 | 7 | -8,48 | 0,71 | 1,47 % | -1 |

Le preset `SL -0,39 + BE à P0` a été sélectionné et gelé avant l'ouverture de la fenêtre suivante.

### Hors échantillon

Fenêtre : `2026-05-01 → 2026-07-01`, jamais utilisée pour choisir les paramètres du candidat.

| Trades | Gagnants | Net USD | PF | Payoff | DD equity max | OnTester |
|---:|---:|---:|---:|---:|---:|---:|
| 48 | 5 | -21,87 | 0,67 | -0,46 | 1,74 % | -1 |

Le candidat échoue : résultat net négatif, facteur de profit inférieur à 1 et score `OnTester` rejeté. Aucun autre candidat ne doit être choisi a posteriori sur cette même fenêtre comme s'il s'agissait encore d'un OOS vierge.

## Données 2025 rejetées

MetaQuotes-Demo n'a pas fourni de ticks réels XAUUSD pour 2025. Les deux rapports annuels affichent `0% ticks réel`; leurs résultats, même positifs, sont invalides au regard du protocole et ne sont utilisés dans aucune décision.

## Suite requise

1. Confirmer le marché exact : les captures montrent le future Micro Gold `MGC`, alors que les tests MT5 ci-dessus portent sur le CFD spot `XAUUSD` de MetaQuotes-Demo.
2. Utiliser le symbole exact et l'historique de ticks du broker réellement visé, avec commission, spread et taille de contrat correspondants.
3. Réserver une nouvelle période vierge pour le forward test ; ne pas réutiliser mai–juin 2026 comme OOS.
4. Garder Algo Trading désactivé tant qu'une variante n'a pas passé compilation, vrais ticks, OOS, coûts dégradés et forward démo.

Les rapports bruts sont archivés dans [`artifacts/validation-2026-08-04`](../artifacts/validation-2026-08-04/).

