# RSI Fibonacci Retracement EA — infrastructure de recherche V3 (MT5)

## ⚠️ Avertissement et Réserve de Risque

**CE ROBOT EST EXCLUSIVEMENT DESTINÉ À UN USAGE EN COMPTE DÉMO METATRADER 5.**

Le trading d'instruments financiers comporte des risques élevés de perte en capital. Les performances passées ou les simulations de backtest ne garantissent aucunement les résultats futurs. Aucune promesse de rentabilité n'est formulée. Cette version doit rester en démo tant que sa compilation, ses backtests hors échantillon et son suivi forward n'ont pas été validés.

**État au 6 août 2026 :** la compilation et les 111 tests techniques passent. La V3.1 ajoute une **géométrie adaptative** qui ajuste le stop-loss et le take-profit à la volatilité réelle du graphique (ATR), au lieu de s'appuyer uniquement sur des ratios Fibonacci fixes. Le preset `RSIFibEA_adaptive_xau_m15.set` active cette géométrie adaptative avec tous les filtres V2. Le gate de coûts broker reste un prérequis pour tout forward test. Voir [`docs/MARKET_AND_ACCOUNT_GATE_V3.md`](docs/MARKET_AND_ACCOUNT_GATE_V3.md).

---

## 1. Description & Objectif

L'**RSIFibRetracementEA** est un Expert Advisor (EA) développé en MQL5 pour MetaTrader 5. Il automatise une stratégie basée sur :
1. La détection d'une **sortie de zone de survente / surachat** de l'indicateur RSI sur bougies clôturées (`shift 1` et `shift 2`).
2. La détection d'un **ancrage Fibonacci personnalisé** sur la première bougie de couleur opposée clôturée.
3. Le placement d'un **ordre limite** sur un niveau de retracement sous le niveau 0 (`-0.21` par défaut), protégé par un Stop-Loss au niveau d'invalidation (`-0.29` par défaut) et visant une extension à `2.56` (`2.64` en ligne visuelle).
4. Un cadrage du risque monétaire basé sur un pourcentage de l'Equity (0,10 % par défaut, plafond logiciel 0,25 %), estimé par `OrderCalcProfit` avec coûts et slippage conservateurs, puis arrondi vers le bas au pas de volume du symbole.

La V2 ajoute, sous forme de modules **opt-in** désactivés par défaut, une qualification de l'excursion RSI, un filtre de tendance EMA/RSI sur timeframe supérieur, un filtre de régime ATR rapide/lent et un break-even structurel déclenché par un ratio Fibonacci. Elle remplace aussi le scan broker à chaque tick par une réconciliation événementielle temporisée, bloque les snapshots ambigus dans `STATE_FAULT`, contrôle SL/TP périodiquement, expose un score `OnTester` plafonné et fournit un dashboard léger.

Le preset conservateur garde tous les modules stratégiques V2 coupés afin de préserver le comportement de référence. Le preset `RSIFibRetracementEA_v2_research.set` les active à faible risque sur un signal **M15** et une tendance **H1**, uniquement comme hypothèse de recherche, jamais comme preuve de rentabilité.

Avec les ratios par défaut, la distance entrée→stop ne représente que `0,08 × range`, contre `2,77 × range` jusqu'au TP : le ratio rendement/risque théorique est très élevé, mais le stop est extrêmement sensible au spread, au slippage et au bruit de marché. Le filtre `InpMaxSpreadRiskPct` est donc activé par défaut.

---

## 2. Installation dans MetaTrader 5

1. **Localisation des fichiers du projet** :
   - EA : [`MQL5/Experts/RSIFibRetracementEA.mq5`](MQL5/Experts/RSIFibRetracementEA.mq5)
   - Preset conservateur : [`presets/RSIFibRetracementEA_demo.set`](presets/RSIFibRetracementEA_demo.set)
   - Preset de recherche V2 : [`presets/RSIFibRetracementEA_v2_research.set`](presets/RSIFibRetracementEA_v2_research.set)
   - Preset adaptatif (SL/TP dépendent du graphique) : [`presets/RSIFibEA_adaptive_xau_m15.set`](presets/RSIFibEA_adaptive_xau_m15.set)

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
| | `InpRiskPercent` | `0.10` | Risque monétaire par trade en % de l'Equity ; plafond logiciel 0,25 %. |
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
5. **Filtres et gestion V2** :
   - Les filtres sont évalués une fois au signal, uniquement avec des données clôturées, et échouent fermés si une donnée manque.
   - Le break-even utilise `Bid` pour un achat et `Ask` pour une vente, respecte le tick size, les niveaux `STOPS/FREEZE`, conserve le TP et vérifie le retcode broker.
   - Après redémarrage, le range est reconstruit depuis le prix limite historique (ou le fill réel en fallback) et le TP ; le SL courant peut donc déjà être à break-even sans corrompre la géométrie originale.
6. **Runtime défensif** :
   - `OnTradeTransaction` marque seulement l'état broker comme à resynchroniser. Le snapshot exhaustif est coalescé sur le tick suivant ou le watchdog.
   - Plusieurs positions/ordres gérés, un type inattendu ou une exposition étrangère mélangée placent l'EA en `STATE_FAULT` et interdisent toute nouvelle entrée.
7. **Géométrie adaptative (V3.1)** :
   - Avec `InpUseAdaptiveSL=true`, après le calcul Fibonacci initial, l'EA lit l'ATR(14) du graphique en cours. Si la distance entrée→stop est plus petite que `InpMinSLATRMultiple × ATR`, le stop est élargi pour sortir du bruit du spread et de la microstructure.
   - Avec `InpUseAdaptiveTP=true`, le TP est recalculé à `InpTPRiskMultiple × distance_SL_réelle`, garantissant un ratio rendement/risque constant quel que soit l'instrument ou la volatilité du moment.
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

Le manifeste de données est dans [`docs/DATA_MANIFEST_V3.md`](docs/DATA_MANIFEST_V3.md). Le prompt directeur Codex/Gemini est [`MASTER_RESEARCH_PROMPT_V3.md`](MASTER_RESEARCH_PROMPT_V3.md).
Les garde-fous ajoutés au source courant et leur compilation sont consignés dans [`docs/SAFETY_PATCH_V3.md`](docs/SAFETY_PATCH_V3.md).
Le verdict consolidé est [`docs/VALIDATION_REPORT_V3.md`](docs/VALIDATION_REPORT_V3.md).
