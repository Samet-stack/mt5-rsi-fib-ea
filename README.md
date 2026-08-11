# RSI Fibonacci Retracement EA — recherche V4.40 pour MT5

[![Tests Python](https://github.com/Samet-stack/mt5-rsi-fib-ea/actions/workflows/ci.yml/badge.svg)](https://github.com/Samet-stack/mt5-rsi-fib-ea/actions/workflows/ci.yml)
![Usage](https://img.shields.io/badge/usage-tester%20%2F%20d%C3%A9mo%20uniquement-blue)
![Validation](https://img.shields.io/badge/performance-non%20valid%C3%A9e-orange)

## ⚠️ Avertissement et Réserve de Risque

**CE ROBOT EST EXCLUSIVEMENT DESTINÉ À UN USAGE EN COMPTE DÉMO METATRADER 5.**

Le trading d'instruments financiers comporte des risques élevés de perte en capital. Les performances passées ou les simulations de backtest ne garantissent aucunement les résultats futurs. Aucune promesse de rentabilité n'est formulée. Cette version doit rester en démo tant que sa compilation, ses backtests hors échantillon et son suivi forward n'ont pas été validés.

**État au 11 août 2026 :** la V4.40 passe 162 tests locaux et compile avec 0 erreur / 0 avertissement dans MetaEditor build 6090. Elle ajoute le sizing dynamique par trade, un break-even couvrant les coûts vérifiés, un trailing en multiples du risque initial et des limites partagées Gold/Nasdaq/EURUSD. Les essais de développement de juillet obtiennent une fréquence suffisante sur Gold + Nasdaq, mais échouent le gate de robustesse après le scénario de coûts utilisé : la rentabilité n'est **pas résolue**. Janvier et juillet 2026 sont désormais des fenêtres contaminées par le développement. Tous les presets publics restent bloqués par `InpCostModelVerified=false`. Voir le [`rapport multi-marchés V4.40`](docs/V440_MULTI_MARKET_RESEARCH.md), le [`rapport d'ablation V4.30`](docs/JAN_2026_V430_ABLATION.md) et [`docs/MARKET_AND_ACCOUNT_GATE_V3.md`](docs/MARKET_AND_ACCOUNT_GATE_V3.md).

---

## 1. Description & Objectif

L'**RSIFibRetracementEA** est un Expert Advisor (EA) développé en MQL5 pour MetaTrader 5. Il automatise une stratégie basée sur :
1. La détection d'une **sortie de zone de survente / surachat** de l'indicateur RSI sur bougies clôturées (`shift 1` et `shift 2`).
2. La détection d'un **ancrage Fibonacci personnalisé** sur la première bougie de couleur opposée clôturée.
3. Le placement d'un **ordre limite** sur un niveau de retracement sous le niveau 0 (`-0.21` par défaut), protégé par un Stop-Loss au niveau d'invalidation (`-0.29` par défaut) et visant une extension à `2.56` (`2.64` en ligne visuelle).
4. Un cadrage du risque monétaire basé sur un pourcentage de l'Equity (0,25 % par défaut ; plafond logiciel de 5 % réservé au Strategy Tester et déconseillé au-dessus de 0,25 %), estimé par `OrderCalcProfit` avec coûts et slippage conservateurs, puis arrondi vers le bas au pas de volume du symbole.

Les versions V2 à V4.40 ajoutent des modules **opt-in** : qualification RSI, tendance multi-timeframe, régime ATR, divergence RSI, vrai break de structure, calendrier live ou fichier testeur, géométrie adaptative, break-even, trailing Fibonacci ou en multiples de R, sortie de stagnation et prise partielle. La V4.40 ajoute des plafonds portefeuille par plage de magic numbers, un plancher break-even calculé en devise du compte et des profils distincts Gold/Nasdaq/EURUSD. La réconciliation broker bloque les snapshots ambigus dans `STATE_FAULT` et protège la reprise après redémarrage. Une fonctionnalité implémentée n'est jamais présentée comme une preuve de performance.

Le preset conservateur garde tous les modules stratégiques V2 coupés afin de préserver le comportement de référence. Le preset `RSIFibRetracementEA_v2_research.set` les active à faible risque sur un signal **M15** et une tendance **H1**, uniquement comme hypothèse de recherche, jamais comme preuve de rentabilité.

Avec les ratios par défaut, la distance entrée→stop ne représente que `0,08 × range`, contre `2,77 × range` jusqu'au TP : le ratio rendement/risque théorique est très élevé, mais le stop est extrêmement sensible au spread, au slippage et au bruit de marché. Le filtre `InpMaxSpreadRiskPct` est donc activé par défaut.

---

## 2. Installation dans MetaTrader 5

1. **Localisation des fichiers du projet** :
   - EA : [`MQL5/Experts/RSIFibRetracementEA.mq5`](MQL5/Experts/RSIFibRetracementEA.mq5)
   - Preset conservateur : [`presets/RSIFibRetracementEA_demo.set`](presets/RSIFibRetracementEA_demo.set)
   - Preset de recherche V2 : [`presets/RSIFibRetracementEA_v2_research.set`](presets/RSIFibRetracementEA_v2_research.set)
   - Preset adaptatif (SL/TP dépendent du graphique) : [`presets/RSIFibEA_adaptive_xau_m15.set`](presets/RSIFibEA_adaptive_xau_m15.set)
   - Profils portefeuille de recherche : [`Gold`](presets/RSIFibEA_gold_m15_portfolio_research.set), [`Nasdaq / USTEC`](presets/RSIFibEA_nasdaq_m15_portfolio_research.set), [`EURUSD`](presets/RSIFibEA_eurusd_m15_portfolio_research.set)

2. **Copie dans le répertoire MetaTrader 5** :
   - Dans MT5, ouvrir le menu **Fichier** > **Ouvrir le dossier des données** (`Open Data Folder`).
   - Copier `RSIFibRetracementEA.mq5` dans le dossier `MQL5/Experts/RSIFibEA/`.
   - Copier les fichiers `.set` dans `MQL5/Profiles/Tester/` afin que `ExpertParameters` puisse les résoudre sans chemin absolu.

3. **Compilation dans MetaEditor** :
   - Dans MT5, appuyer sur **F4** pour ouvrir MetaEditor.
   - Ouvrir `RSIFibRetracementEA.mq5` dans l'arborescence des Experts.
   - Appuyer sur **F7** (Compiler). Vérifier l'absence d'erreurs dans l'onglet *Toolbox / Errors*.
   - Sous Windows, [`tools/deploy_compile_mt5.ps1`](tools/deploy_compile_mt5.ps1) automatise la détection du dossier de données, la copie, la compilation native et le contrôle `0 errors, 0 warnings`.

4. **État actuel** :
   - Utiliser uniquement le Strategy Tester, avec les agents locaux.
   - Ne pas attacher l'EA pour exécution et ne pas cocher **Autoriser le trading algorithmique** tant que le Gate 0 et les coûts ne sont pas validés.

---

## 3. Paramètres de Configuration (Inputs)

| Groupe | Paramètre | Valeur par défaut | Description |
| :--- | :--- | :--- | :--- |
| **Garde & Risque** | `InpDemoOnly` | `true` | Sécurité : bloque l'exécution si le compte n'est pas un compte Démo MT5. |
| | `InpMagicNumber` | `20260803` | Identifiant unique des ordres et positions de cet EA. |
| | `InpPortfolioMagicMin` / `InpPortfolioMagicMax` | `0` / `0` | Plage de magic numbers partageant les limites portefeuille ; zéro désactive ce regroupement. |
| | `InpMaxPortfolioActiveExposures` / `InpMaxPortfolioDailyTrades` | `0` / `0` | Plafonds tous symboles pour les positions + ordres actifs et les nouvelles positions du jour. |
| | `InpMaxPortfolioDailyLossPct` | `0.0` | Plafond journalier partagé incluant PnL réalisé, commissions, swap, frais et flottant. |
| | `InpRiskPercent` | `0.25` | Risque monétaire par trade en % de l'Equity. Le plafond logiciel est 5 %, uniquement pour recherches tester ; les valeurs supérieures à 0,25 % ne sont pas recommandées et plusieurs presets historiques en contiennent. |
| | `InpMaxDailyLossPct` | `1.0` | Plafond de perte/drawdown journalier maximal en % de l'Equity. |
| | `InpMaxDailyTrades` | `2` | Nombre maximal de nouveaux trades/positions par jour (0 = illimité). |
| | `InpMaxConsecutiveLosses` | `2` | Nombre maximal de pertes consécutives par jour (0 = illimité). |
| | `InpMaxSpreadPoints` | `0` | Filtre de spread max en points (0 = désactivé). |
| | `InpMaxSpreadRiskPct` | `25.0` | Refuse une entrée si le spread dépasse ce pourcentage de la distance entrée→SL. |
| | `InpCloseUnprotectedPosition` | `true` | Ferme en sécurité une position de cet EA si son SL ou son TP broker disparaît. |
| | `InpStateWatchdogMs` | `1000` | Filet de sécurité de réconciliation broker ; les transactions déclenchent aussi une synchronisation immédiate. |
| | `InpCostModelVerified` | `false` | Gate explicite : reste faux tant que le barème du broker n'est pas documenté. C'est ce flag qui bloque les presets actuels. |
| | `InpEstimatedRoundTurnCostPerLot` | `0.0` | Commission/frais aller-retour vérifiés, en devise du compte et par lot. Zéro est accepté seulement si le broker confirme réellement zéro ; une réserve conservatrice doit sinon être justifiée. |
| | `InpAdverseEntrySlippageTicks` / `InpAdverseStopSlippageTicks` | `1` / `1` | Slippage adverse ajouté à l'entrée et au stop dans le pire cas de sizing. |
| | `InpMaxFreeMarginUsagePct` | `25.0` | Refuse l'ordre si `OrderCalcMargin` dépasse cette part de la marge libre. |
| | `InpMinDaysToContractExpiry` | `7` | Cutoff futures : refuse toute nouvelle exposition, impose une expiration pending antérieure puis aplatit l'exposition gérée au cutoff ; sans effet sur un CFD sans expiry. |
| **Filtre Session** | `InpUseSessionFilter` | `false` | Filtre d'heure de trading (désactivé par défaut). |
| | `InpStartHour` | `8` | Heure de début de session (heure broker). |
| | `InpEndHour` | `20` | Heure de fin de session (heure broker). |
| **Indicateur RSI**| `InpRSI_Period` | `14` | Période du RSI. |
| | `InpRSI_AppliedPrice` | `PRICE_CLOSE` | Prix appliqué au calcul du RSI. |
| | `InpSignalTimeframe` | `PERIOD_CURRENT` | Timeframe de calcul ; le graphique courant est utilisé par défaut. |
| | `InpOversoldLevel` | `30.0` | Seuil de survente (déclencheur signal Achat si croisement hausse). |
| | `InpOverboughtLevel` | `70.0` | Seuil de surachat (déclencheur signal Vente si croisement baisse). |
| **Qualité RSI** | `InpUseRSIQualityFilter` | `false` | Exige une excursion consécutive en zone et une vitesse minimale de sortie. |
| | `InpRSIMinBarsInZone` / `InpRSIMinExitDelta` | `2` / `4.0` | Profondeur temporelle et impulsion minimales, sur bougies clôturées. |
| **Divergence RSI** | `InpUseRSIDivergence` / `InpRequireRSIDivergence` | `false` / `false` | Détecte ou exige une divergence sur pivots clôturés ; module expérimental. |
| **Calendrier** | `InpNewsMode` | `NEWS_DISABLED` (`0`) | `0` désactivé, `1` calendrier live, `2` fichier testeur déterministe. Le live est interdit dans Strategy Tester et les erreurs fichier/API échouent fermées. |
| | `InpTesterNewsFile` | `RSIFibEA\news_events_v1.csv` | Chemin relatif dans `Terminal/Common/Files` ; schéma et heure serveur documentés dans [`docs/NEWS_TESTER_FILE.md`](docs/NEWS_TESTER_FILE.md). |
| **Structure** | `InpUseMarketStructure` / `InpUseSweepBuffer` | `false` / `false` | Filtres optionnels de structure et de buffer derrière les mèches récentes. |
| **Temps/week-end** | `InpUseStagnationExit` / `InpFridayFilter` | `false` / `true` | Sortie optionnelle des positions stagnantes et restrictions de fin de semaine. |
| **Tendance MTF** | `InpUseMTFTrendFilter` | `false` | Confirme le sens par le Close HTF face à son EMA. |
| | `InpMTFTimeframe` / `InpMTFEMAPeriod` | `H1` / `200` | Timeframe strictement supérieur et période EMA. |
| | `InpMTFUseRSIConfirm` | `false` | Ajoute, si activé, un RSI HTF de part et d'autre de sa médiane. |
| **Régime volatilité** | `InpUseVolatilityRegime` | `false` | Filtre le ratio ATR rapide / ATR lent. |
| | `InpVolMinRatio` / `InpVolMaxRatio` | `0.80` / `2.20` | Bornes inclusives du régime accepté. |
| **Ancrage & Timing**| `InpMinImpulseBars` | `1` | Bougies minimales écoulées après le signal avant de chercher l'ancrage. |
| | `InpAnchorWaitBars` | `8` | Nombre max de bougies d'attente pour la bougie d'ancrage opposée. |
| | `InpPendingOrderBars` | `8` | Durée de vie maximale de l'ordre limite en nombre de bougies. |
| | `InpMinRangeATR` / `InpMaxRangeATR` | `0.0` | Bornes de filtre de taille de range en multiples d'ATR (0 = désactivé). |
| **Géométrie Fib** | `InpEntryRatio` | `-0.21` | Ratio du prix d'entrée limite (< 0). |
| | `InpStopRatio` | `-0.29` | Ratio du Stop-Loss d'invalidation (< EntryRatio). |
| | `InpTargetRatio` | `2.56` | Ratio du Take-Profit principal. |
| | `InpVisualTargetRatio` | `2.64` | Ratio de la seconde borne visuelle affichée. |
| **Géométrie Adaptative** | `InpUseAdaptiveSL` | `false` | Si activé, le SL s'adapte à la volatilité du graphique : si la distance Fib SL est plus petite que `InpMinSLATRMultiple × ATR(14)`, le stop est élargi automatiquement pour rester hors du bruit. |
| | `InpMinSLATRMultiple` | `1.5` | Plancher du SL en multiples d'ATR. Le SL ne sera jamais plus proche que cette distance × ATR de l'entrée. |
| | `InpUseAdaptiveTP` | `false` | Si activé, le TP est calculé comme un multiple fixe de la distance SL réelle (ratio rendement/risque constant). |
| | `InpTPRiskMultiple` | `3.0` | TP = distance SL × ce multiple. Avec `3.0` et un SL de 1.5 ATR, le TP sera à 4.5 ATR de l'entrée. |
| **Gestion position** | `InpUseBreakEven` | `false` | Déplace une seule fois le SL sans jamais le détériorer. |
| | `InpBETriggerFibRatio` / `InpBEOffsetTicks` | `1.00` / `1` | Déclencheur structurel et verrou favorable en ticks. |
| | `InpBreakEvenCoversCosts` | `true` | Calcule avec `OrderCalcProfit` le prix couvrant le coût aller-retour vérifié avant d'ajouter l'offset. |
| | `InpUseFibTrailingStop` | `false` | Trailing Stop Fibonacci multi-niveaux : verrouille les gains progressivement (BE à Fib 0.382, P0 à Fib 0.618, Fib 0.382 à Fib 1.000, Fib 1.000 à Fib 1.618, Fib 1.618 à Fib 2.000). |
| | `InpUseRiskTrailingStop` | `false` | Trailing indépendant du symbole, déclenché et déplacé par paliers en multiples de la distance initiale entrée→SL. Incompatible avec le trailing Fibonacci. |
| | `InpRiskTrailTriggerR` / `InpRiskTrailLockR` / `InpRiskTrailStepR` | `1.0` / `0.0` / `0.5` | Premier déclenchement, gain verrouillé initial et pas du trailing R. |
| | `InpUsePartialTP` | `false` | Ferme une fraction normalisée du volume au premier objectif, puis gère le reliquat ; module expérimental. |
| **Affichage** | `InpDrawChartObjects` | `true` | Dessine les 6 lignes horizontales de la structure sur le graphique. |
| | `InpVerboseLog` | `true` | Journalisation détaillée dans le Journal d'Experts. |
| | `InpShowDashboard` | `true` | Résumé runtime mis à jour au plus une fois par seconde. |
| **Optimisation** | `InpTesterMinTrades`, `InpTesterTargetTrades`, `InpTesterMaxDDPct` | `40`, `120`, `30.0` | Garde du score technique `OnTester` historique seulement. Le diagnostic V3 applique séparément un plancher conservateur de 100, qui ne remplace pas une analyse de puissance. |

---

## 4. Logique et Fonctionnement de la Stratégie

```text
 IDLE ──signal──> WAITING_FOR_ANCHOR ──ancre──> PENDING_ORDER ──fill──> IN_POSITION ──close──> IDLE
                                      snapshot ambigu / protection invalide ──> STATE_FAULT
```

1. **Signal RSI (sur bougies clôturées)** :
   - **Achat** : `RSI[2] <= 30` et `RSI[1] > 30`.
   - **Vente** : `RSI[2] >= 70` et `RSI[1] < 70`.
2. **Ancrage déterministe** :
   - On attend la première bougie fermée de couleur opposée (`Close < Open` pour Achat, `Close > Open` pour Vente).
   - **Achat** : `P1` = plus haut High entre la bougie signal et la bougie de retracement ; `P0` = Low de la bougie baissière.
   - **Vente** : `P1` = plus bas Low entre la bougie signal et la bougie de retracement ; `P0` = High de la bougie haussière.
3. **Placements & Protections** :
   - Calcul des 4 niveaux : `Entry`, `Stop`, `Target`, `VisualTarget`.
   - Vérification anti-repaint et validation stricte : l'ordre `Buy Limit` n'est envoyé que si `Entry < Ask`, le `Sell Limit` si `Entry > Bid`. Aucun ordre au marché de substitution.
   - Taille de lot calculée par `OrderCalcProfit` après dégradation de l'entrée et du stop, ajout du coût aller-retour par lot, contrôle exact après arrondi et validation `OrderCalcMargin`.
4. **Expirations & Annulations** :
   - Expiration automatique après `InpPendingOrderBars` bougies.
   - Annulation si le prix touche/dépasse l'invalidation avant l'exécution.
   - Annulation si un signal RSI opposé se confirme.
   - Annulation si le plafond de perte journalière ou de trades max est atteint.
   - Annulation si risque journalier, spread, session ou cycle du contrat deviennent invalides après placement. Une course broker entre fill et annulation reste possible et doit être stressée.
   - Expiration serveur finie prioritaire. Pour un future, la durée pending complète doit finir avant le cutoff d'échéance et GTC seul est refusé.
   - Au cutoff, redémarrer l'EA ne l'abandonne pas : il reste en gestion seulement, annule le pending et tente d'aplatir la position avec contrôle du retcode et retry. Une fermeture cliente reste impossible à garantir si MT5/VPS est hors ligne ; les protections broker demeurent indispensables.
   - Au redémarrage, restauration de la direction, de l'heure, de l'entrée, du SL, du TP et de la géométrie depuis l'ordre broker.
5. **Filtres et gestion V2–V4.40** :
   - Les filtres sont évalués séquentiellement au signal, uniquement avec des données clôturées. Chaque croisement reçoit un premier motif de rejet stable dans le résumé `FUNNEL|reason|count`.
   - Le break-even utilise `Bid` pour un achat et `Ask` pour une vente, respecte le tick size, les niveaux `STOPS/FREEZE`, conserve le TP et vérifie le retcode broker.
   - Le sizing n'utilise pas un lot fixe : il recalcule le volume de chaque setup à partir de l'equity, de la distance réelle du stop, des propriétés du symbole, du coût, du slippage et de la marge disponible.
   - Le trailing R conserve le stop initial immuable, y compris après redémarrage, et son plancher ne peut pas être inférieur au break-even couvrant les coûts.
   - Gold, Nasdaq et EURUSD peuvent partager un plafond d'exposition, de trades et de perte journalière via leur plage de magic numbers.
   - Après redémarrage, le range est reconstruit depuis le prix limite historique (ou le fill réel en fallback) et le TP ; le SL courant peut donc déjà être à break-even sans corrompre la géométrie originale.
6. **Runtime défensif** :
   - `OnTradeTransaction` marque seulement l'état broker comme à resynchroniser. Le snapshot exhaustif est coalescé sur le tick suivant ou le watchdog.
   - Plusieurs positions/ordres gérés, un type inattendu ou une exposition étrangère mélangée placent l'EA en `STATE_FAULT` et interdisent toute nouvelle entrée.
7. **Géométrie adaptative (V3.1)** :
   - Avec `InpUseAdaptiveSL=true`, après le calcul Fibonacci initial, l'EA lit l'ATR(14) du graphique en cours. Si la distance entrée→stop est plus petite que `InpMinSLATRMultiple × ATR`, le stop est élargi pour sortir du bruit du spread et de la microstructure.
   - Avec `InpUseAdaptiveTP=true`, le TP est recalculé à `InpTPRiskMultiple × distance_SL_réelle`. Cela fixe le ratio géométrique demandé avant fill et avant coûts, sans garantir le résultat réalisé.
   - Les deux options sont désactivées par défaut pour préserver la compatibilité avec les presets V1/V2. Le preset [`RSIFibEA_adaptive_xau_m15.set`](presets/RSIFibEA_adaptive_xau_m15.set) les active avec tous les filtres V2.

---

## 5. Procédure de Backtest MT5

1. Ouvrir le **Testeur de Stratégie MT5** (`Ctrl + R`).
2. Sélectionner `RSIFibRetracementEA.mq5` (ou `.ex5`).
3. Choisir le symbole (ex. `EURUSD`) et le timeframe (ex. `M15`).
4. Sélectionner impérativement **Chaque tick basé sur des ticks réels** (*Every tick based on real ticks*). Le mode OHLC n'est pas acceptable avec ce stop très serré.
5. Dans l'onglet **Inputs**, charger le preset `presets/RSIFibRetracementEA_demo.set` (ratios Fib fixes) ou `presets/RSIFibEA_adaptive_xau_m15.set` (SL/TP adaptés au graphique via ATR, tous filtres V2 actifs).
6. Documenter le modèle de coûts du broker cible puis seulement passer `InpCostModelVerified=true`. Un montant nul n'est admis que si le broker confirme réellement l'absence de commission/frais ; les presets livrés restent volontairement bloqués avec le flag à `false`.
7. Réaliser des tests hors échantillon (*Out of Sample*), puis un walk-forward et une simulation avec coûts dégradés avant tout déploiement en démo. Le protocole détaillé se trouve dans [`docs/BACKTEST_PROTOCOL.md`](docs/BACKTEST_PROTOCOL.md).

Le fichier [`tools/mt5_smoke_eurusd_m15.ini`](tools/mt5_smoke_eurusd_m15.ini) fournit en plus un contrôle technique minimal, sans identifiants : EURUSD M15, juillet 2026, dépôt simulé de 3 000 USD, levier 1:100, vrais ticks, aucune optimisation, agents locaux uniquement et fermeture automatique. Ce smoke test vérifie l'exécution ; il ne mesure pas encore la rentabilité de la stratégie.

[`tools/mt5_smoke_eurusd_m15_v2.ini`](tools/mt5_smoke_eurusd_m15_v2.ini) reprend exactement la même fenêtre avec le preset de recherche V2 à 0,10 % de risque, pour une comparaison technique à données constantes.

Pour répéter proprement des fenêtres ou symboles différents, [`tools/run_mt5_backtest.ps1`](tools/run_mt5_backtest.ps1) génère une configuration sans identifiants, interdit le trading live et les DLL, force les ticks réels et les agents locaux, puis vérifie que MT5 a bien produit un nouveau rapport. Le script refuse de forcer la fermeture d'une instance MT5 bloquée.

---

## 6. Passage en démo — actuellement interdit par le Gate 0

La garde de code accepte uniquement le Strategy Tester ou un compte MT5 classé démo, mais cela ne suffit pas à autoriser un forward test. Il faut d'abord choisir l'instrument exact, sonder le broker cible, intégrer son barème de coûts et satisfaire les gates décrits dans [`docs/EXPERIMENT_PLAN_V3.md`](docs/EXPERIMENT_PLAN_V3.md). Aucune transition vers le réel n'est automatique.

---

## 7. Validation Mathématique Locale (Tests Python)

Le projet intègre une suite de tests unitaires indépendants vérifiant l'exactitude des formules et règles de risque :

```bash
python3 -m unittest discover -s tests -v
```

La suite couvre les formules achat/vente, les filtres V2, le break-even, le score `OnTester`, le dimensionnement, la restauration, le parseur MT5, le diagnostic et le registre append-only. Ces tests ne remplacent ni la compilation MetaEditor ni le testeur MT5.

Les diagnostics V3 doivent passer par le harness enregistré :

```bash
python3 tools/experiment_registry.py --root artifacts/experiments_v3 verify
```

`tools/run_registered_diagnostic.py` refuse un source, preset, rapport ou probe dont le hash ne correspond pas à la spec immuable. La spec historique ne peut donc pas être réutilisée avec le nouveau source V3 ; les copies exactes restent archivées dans chaque run.

La couche V4 ajoute :

- [`tools/archive_mt5_run.py`](tools/archive_mt5_run.py), qui refuse l'écrasement, compare les 101 paramètres effectifs au preset et hash chaque artefact ;
- [`tools/cost_adjustment.py`](tools/cost_adjustment.py), qui agrège les sorties partielles, conserve commission/swap/frais natifs une seule fois et n'ajoute jamais une seconde fois le spread déjà implicite ;
- [`tools/portfolio_evaluator.py`](tools/portfolio_evaluator.py), qui exige un coût explicite par symbole, des fenêtres identiques et au moins 99 % de ticks réels avant de calculer fréquence, profit factor, stress et concentration ;
- [`tools/run_mt5_symbol_catalog.ps1`](tools/run_mt5_symbol_catalog.ps1), qui découvre en mode testeur les symboles réellement disponibles sans envoyer d'ordre ;
- les sept archives de [`artifacts/experiments_v4/runs`](artifacts/experiments_v4/runs), liées au rapport d'ablation janvier 2026.

Le manifeste de données est dans [`docs/DATA_MANIFEST_V3.md`](docs/DATA_MANIFEST_V3.md). Le prompt directeur Codex/Gemini est [`MASTER_RESEARCH_PROMPT_V3.md`](MASTER_RESEARCH_PROMPT_V3.md).
Le snapshot historique des garde-fous V3 est consigné dans [`docs/SAFETY_PATCH_V3.md`](docs/SAFETY_PATCH_V3.md) ; les contrôles du source courant sont ceux de la CI et de la compilation native la plus récente.
Le verdict consolidé est [`docs/VALIDATION_REPORT_V3.md`](docs/VALIDATION_REPORT_V3.md).

---

## 8. Organisation du dépôt

| Chemin | Rôle |
| --- | --- |
| `MQL5/Experts/` | EA principal et sonde de symbole sans ordre |
| `presets/` | configurations de recherche ; toutes bloquées jusqu'à vérification des coûts |
| `tests/` | contrats statiques et tests Python reproductibles |
| `tools/` | compilation, testeur MT5, parsing, diagnostic et registre |
| `artifacts/` | preuves historiques brutes et diagnostics ; pas des prévisions |
| `docs/` | spécifications, protocoles, gates et rapports d'audit |

Les noms historiques de certains presets sont conservés pour la traçabilité.
Des termes comme `champion` ou `target600` dans un nom de fichier ne constituent
ni une recommandation ni une attente de performance.

## 9. Amélioration continue

Le projet évolue par petites hypothèses vérifiables : une modification causale,
des tests, une compilation native, un run préenregistré et une revue des coûts.
Le [plan public](docs/ROADMAP.md) sert de file de travail. « Améliorer chaque
jour » signifie documenter et vérifier les progrès ; cela ne signifie pas
optimiser chaque jour sur les mêmes données ni publier artificiellement un
commit quotidien.

## 10. Contribuer et sécurité

Consultez [CONTRIBUTING.md](CONTRIBUTING.md) avant toute proposition et
[SECURITY.md](SECURITY.md) pour signaler une vulnérabilité sans publier de
secret. Les pull requests qui ajoutent une affirmation de performance doivent
inclure les artefacts reproductibles exigés par le protocole.

Le dépôt est publiquement consultable. Aucune licence open source n'est encore
déclarée : les droits de réutilisation restent réservés jusqu'au choix explicite
d'une licence par le propriétaire.
