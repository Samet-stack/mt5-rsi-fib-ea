# Spécification V2 — moteur avancé, mesurable et compatible V1

## Objectif

La V2 enrichit le moteur sans modifier silencieusement la stratégie de référence. Tous les filtres avancés et la gestion break-even sont indépendants, configurables et désactivés par défaut. Avec ces options à `false`, les signaux, ancrages et niveaux de la V1 doivent rester identiques.

Cette version reste exclusivement destinée à la compilation, au testeur MT5 en ticks réels et au compte démo.

## 1. Filtres de stratégie avancés

### 1.1. Qualité de l’excursion RSI

Inputs :

```text
InpUseRSIQualityFilter = false
InpRSIMinBarsInZone    = 2
InpRSIMinExitDelta     = 4.0
```

Lors d’un signal achat :

- `RSI[1] - RSI[2] >= InpRSIMinExitDelta` ;
- pour chaque shift `s` de `2` à `1 + InpRSIMinBarsInZone`, `RSI[s] <= InpOversoldLevel`.

Pour une vente, les inégalités sont inversées et la vitesse vaut `RSI[2] - RSI[1]`.

Si une donnée demandée est absente, `EMPTY_VALUE` ou non finie, le filtre échoue fermé et le trade est refusé.

### 1.2. Tendance multi-timeframe

Inputs :

```text
InpUseMTFTrendFilter = false
InpMTFTimeframe      = PERIOD_H1
InpMTFEMAPeriod      = 200
InpMTFUseRSIConfirm  = false
InpMTFRSIPeriod      = 14
InpMTFRSIMidline     = 50.0
```

Le filtre utilise exclusivement la dernière bougie **clôturée** du timeframe supérieur (`shift 1`) :

- achat : `Close_HTF[1] > EMA_HTF[1]` et, si activé, `RSI_HTF[1] > Midline` ;
- vente : `Close_HTF[1] < EMA_HTF[1]` et, si activé, `RSI_HTF[1] < Midline`.

Les handles EMA/RSI sont créés une fois dans `OnInit`, jamais par tick. Les données non prêtes refusent le signal sans fallback.

### 1.3. Régime de volatilité

Inputs :

```text
InpUseVolatilityRegime = false
InpVolFastATRPeriod    = 14
InpVolSlowATRPeriod    = 100
InpVolMinRatio         = 0.80
InpVolMaxRatio         = 2.20
```

Sur la bougie clôturée du timeframe de signal :

```text
VolRatio = ATR_fast[1] / ATR_slow[1]
```

Le signal est autorisé seulement si `InpVolMinRatio <= VolRatio <= InpVolMaxRatio`. Le filtre est symétrique achat/vente et échoue fermé.

## 2. Break-even spécifique à la géométrie Fibonacci

Inputs :

```text
InpUseBreakEven          = false
InpBreakEvenTriggerRatio = 1.00
InpBreakEvenOffsetTicks  = 1
```

Le déclencheur est un niveau Fibonacci et non un multiple du risque, car la distance entrée→SL ne vaut que `0,08 × range` avec les ratios actuels.

Pour l’achat :

```text
Trigger = P0 + TriggerRatio × Range
NewSL   = Entry + OffsetTicks × TickSize
```

Pour la vente :

```text
Trigger = P0 - TriggerRatio × Range
NewSL   = Entry - OffsetTicks × TickSize
```

Règles :

- utiliser Bid pour l’achat et Ask pour la vente ;
- aligner le SL sur le tick size dans le sens compatible avec le broker ;
- respecter le maximum de `STOPS_LEVEL` et `FREEZE_LEVEL` ;
- ne jamais éloigner un SL déjà plus protecteur ;
- utiliser l’objet `m_safety_trade`, pas l’objet pending configuré en `ORDER_FILLING_RETURN` ;
- vérifier le booléen et `ResultRetcode()` de `PositionModify` ;
- temporiser les nouvelles tentatives pour éviter le flood.

### Restauration après redémarrage

Une position déjà passée au break-even ne peut plus reconstruire le range depuis son SL courant. La V2 recherche d'abord le prix limite demandé dans l'historique via `POSITION_IDENTIFIER → DEAL_ORDER → ORDER_PRICE_OPEN`; ce prix est insensible à une amélioration d'exécution. Si cet historique n'est pas disponible, elle utilise le prix d'ouverture réel comme fallback. Dans les deux cas, la géométrie vient de l'entrée et du TP inchangé :

```text
Range achat = (TP - Entry) / (TargetRatio - EntryRatio)
Range vente = (Entry - TP) / (TargetRatio - EntryRatio)
```

Le stop original attendu est ensuite recalculé avec `StopRatio` et conservé séparément du SL live. Un stop broker plus risqué que ce stop original déclenche la garde de position non protégée ; un changement de TP ou une signature géométrique incohérente bloque le système dans `STATE_FAULT` sans ouvrir de nouveau risque.

## 3. Runtime événementiel

`OnTradeTransaction` doit rester constant et très court : il marque `m_sync_required = true` et, pour une transaction de deal, invalide le cache des statistiques journalières. Il ne parcourt pas l'historique et n'envoie aucune nouvelle requête de trading, car l'ordre d'arrivée des transactions n'est pas garanti et la file est bornée.

`OnTick` appelle `MaybeSyncState` :

- immédiatement si `m_sync_required == true` ;
- sur nouvelle bougie ;
- sinon au maximum une fois par seconde comme filet de sécurité.

Cette architecture remplace le balayage complet de tous les ordres et positions à chaque tick.

## 4. Dashboard sobre

Le dashboard utilise un seul `Comment()` mis à jour au maximum une fois par seconde et désactivé dans le testeur par défaut. Il affiche seulement : version, compte démo, état, direction, spread, niveaux du setup, filtres actifs et dernier motif synthétique. Aucun accès à l’historique des deals n’est effectué pour rafraîchir l’interface.

## 5. Critère d’optimisation `OnTester`

Inputs de recherche :

```text
InpTesterMinTrades = 40
InpTesterTargetTrades = 120
InpTesterMaxDDPct  = 30.0
InpTesterPFCap     = 5.0
InpTesterSharpeCap = 5.0
```

Un passage renvoie `-1` si : nombre de trades insuffisant, profit net non positif, Sharpe non positif, statistique non finie ou drawdown equity supérieur au plafond.

Pour un passage admissible :

```text
PF       = clamp(ProfitFactor, 0, PFCap)
Sharpe   = clamp(SharpeRatio, 0, SharpeCap)
TradeW   = min(1, sqrt(Trades / TargetTrades))
DDW      = (1 - EquityDDPct / MaxDDPct)²
Score    = Sharpe × sqrt(PF) × TradeW × DDW
```

Le plafonnement empêche un profit factor ou Sharpe extrême issu de quelques trades de dominer l’optimisation. Cette métrique classe les essais ; elle ne valide pas une stratégie sans out-of-sample et walk-forward.

## 6. Critères d’acceptation V2

- Les tests V1 restent verts.
- Des tests purs couvrent chaque filtre dans les deux directions et chaque frontière.
- Les tests de contrat vérifient handles créés/libérés, `OnTradeTransaction` sans opération broker, synchronisation throttled, restauration depuis TP et contrôle des retcodes break-even.
- Avec tous les modules V2 désactivés, les règles V1 sont inchangées.
- Aucun martingale, grid, moyenne à la baisse, ajout de volume ou conversion en ordre marché.
- La compilation MetaEditor doit produire zéro erreur et zéro avertissement avant tout test démo.
