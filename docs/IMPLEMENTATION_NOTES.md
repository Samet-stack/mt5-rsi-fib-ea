# Notes d'Implémentation et Protections — RSIFibRetracementEA

## 1. Hypothèses Déduites et Formalisées

Afin d'obtenir une implémentation 100 % déterministe et répétable à partir des spécifications et captures d'écran, les choix suivants ont été arrêtés et rendus configurables via les paramètres `input` :

1. **Interprétation des Ratios Fibonacci** :
   - Ligne intermédiaire de retracement = `-0.21` (`InpEntryRatio`).
   - Ligne inférieure d'invalidation = `-0.29` (`InpStopRatio`).
   - Premier niveau de cible exécutable = `2.56` (`InpTargetRatio`).
   - Second niveau visuel supérieur = `2.64` (`InpVisualTargetRatio`).
2. **Ancrage P0 et P1** :
   - `P0` (niveau 0.00) est ancré sur l'extrême mèche comprise (`Low` pour achat, `High` pour vente) de la **première bougie de couleur opposée clôturée** après le croisement RSI.
   - `P1` (niveau 1.00) est ancré sur l'extrême mèche comprise (`highest High` pour achat, `lowest Low` pour vente) sur toute la fenêtre allant de la bougie de signal jusqu'à la bougie de retracement incluse.
3. **Anti-Repaint et Clôture de Bougie** :
   - La détection de croisement RSI se fait exclusivement sur bougies fermées (`shift 2` et `shift 1`).
   - Aucun ordre ni calcul de niveau n'utilise les valeurs intrabar de la bougie courante (shift 0).
4. **Ordres Limites stricts** :
   - Un `Buy Limit` exige formellement `Entry < Ask`.
   - Un `Sell Limit` exige formellement `Entry > Bid`.
   - Aucun ordre limite n'est converti silencieusement en ordre au marché (*Market Order*). Si le prix a dépassé l'entrée, le setup est annulé.
5. **Sorties structurelles V4.52** :
   - Le profil Gold fixe l'invalidation au-delà de l'extrême de la bougie d'ancrage clôturée, plus `0,30 ATR`, avec au moins `0,25 ATR` entre entrée et stop.
   - La cible exécutable est `P1` moins un tick dans le sens de l'entrée. Elle provient donc d'une liquidité déjà observée, pas d'un multiple de risque demandé.
   - Le RR brut/net est calculé après ces niveaux et avant le sizing. `InpMinNetRewardRisk` peut refuser un setup mais ne déplace jamais le TP.
   - La séquence est invariantement `niveaux de marché → mesure RR → lot risque/marge`.

---

## 2. Garde-Fous et Mesures de Sécurité

L'EA intègre les mécanismes défensifs suivants :

- **Garde Compte Démo (`InpDemoOnly`)** : Vérification dans `OnInit`. Si `InpDemoOnly=true` et que le mode de compte n'est pas `ACCOUNT_TRADE_MODE_DEMO`, l'initialisation échoue immédiatement avec un log critique.
- **Calcul du Risque Monétaire Réel** : Utilisation prioritaire de `OrderCalcProfit` pour mesurer la perte exacte à 1.0 lot entre `Entry` et `Stop`, puis conversion en volume selon `InpRiskPercent` % de l'Equity. Le volume est arrondi vers le bas au pas de lot (`SYMBOL_VOLUME_STEP`) pour ne jamais excéder le risque toléré.
- **Contrôle du Drawdown et Pertes Journalières** : calcul sur l'historique des deals du jour même (00:00 heure broker), incluant profits, commissions, swaps et frais, complété par le PnL flottant des positions de cet EA. La référence de début de journée est estimée depuis l'equity courante et ce PnL ; une position conservée depuis la veille ou des opérations externes sur le compte peuvent rendre cette estimation imparfaite.
  - Plafond de perte journalière (`InpMaxDailyLossPct`).
  - Nombre maximal de positions ouvertes par jour (`InpMaxDailyTrades`).
  - Séries de pertes consécutives maximales (`InpMaxConsecutiveLosses`).
- **Validation Broker et Distances** : Vérification du spread maximal (`InpMaxSpreadPoints`), des permissions de trading (`TERMINAL_TRADE_ALLOWED`, `MQL_TRADE_ALLOWED`, `SYMBOL_TRADE_MODE`), et respect de `SYMBOL_TRADE_STOPS_LEVEL` et `SYMBOL_TRADE_TICK_SIZE`.
- **Machine d'États et Mutation Sécurisée** : l'état de l'EA (`STATE_IDLE`, `STATE_WAITING_FOR_ANCHOR`, `STATE_PENDING_ORDER`, `STATE_IN_POSITION`, `STATE_FAULT`) dépend des retcodes `CTrade`. Une annulation échouée conserve l'état pending et sera retentée. Un snapshot exhaustif ambigu bloque toute nouvelle prise de risque au lieu de choisir arbitrairement le premier ticket.
- **Réconciliation événementielle** : `OnTradeTransaction` ne fait que poser `m_sync_required`. Le scan positions/ordres est coalescé au tick suivant, sur nouvelle bougie ou au watchdog, au lieu d'être exécuté à chaque tick. La protection SL/TP est tout de même revalidée à chaque réconciliation.
- **Filtres avancés opt-in** : qualité de sortie RSI, tendance EMA/RSI HTF et régime ATR rapide/lent utilisent exclusivement des bougies clôturées, des handles persistants et un comportement fail-closed. Le candidat Gold active la qualité RSI et le régime de volatilité ; les autres presets gardent leurs choix explicites.
- **Break-even structurel** : déclenchement sur ratio Fibonacci, SL monotone aligné au tick, contrôle `STOPS_LEVEL/FREEZE_LEVEL`, modification via l'objet de sécurité et validation du retcode. La reconstruction après redémarrage utilise entrée + TP et jamais le SL modifié.
- **Protection Anti-Martingale** : Interdiction totale de grille, martingale, pyramide, moyenne à la baisse ou rattrapage de pertes. Une seule position ou ordre actif par symbole et Magic Number.
- **Position sans protection** : si une position appartenant à cet EA est retrouvée sans SL ou TP broker valide, `InpCloseUnprotectedPosition=true` déclenche une fermeture de sécurité avec contrôle du retcode. Un objet `CTrade` séparé utilise le filling marché du symbole ; l'objet des ordres pending conserve `ORDER_FILLING_RETURN`. Cette garde est destinée au compte démo et peut être désactivée explicitement pour le diagnostic.

---

## 3. État de la Compilation et Prochaines Étapes MetaEditor

- **Tests locaux** : les suites [`tests/test_strategy_math.py`](../tests/test_strategy_math.py), [`tests/test_source_contract.py`](../tests/test_source_contract.py) et [`tests/test_ai_context_manifest.py`](../tests/test_ai_context_manifest.py) valident géométrie, filtres V2, break-even, fitness, floor de volume, restauration, invariants du source et génération du contexte IA compact. Elles ne prouvent pas la compatibilité binaire MQL5.
- **Compilation MQL5** : la V4.52 a été déployée depuis WSL vers MT5 Windows et compilée nativement avec MetaEditor build 6090 : `0 errors, 0 warnings`. Le hash exact est conservé dans les manifests V4.52.
- **Procédure de validation MetaEditor** :
  1. Ouvrir MT5 et lancer MetaEditor (`F4`).
  2. Ouvrir le fichier [`MQL5/Experts/RSIFibRetracementEA.mq5`](../MQL5/Experts/RSIFibRetracementEA.mq5).
  3. Appuyer sur **F7** pour compiler.
  4. Lancer le testeur de stratégie en ticks réels avec le preset [`presets/RSIFibRetracementEA_demo.set`](../presets/RSIFibRetracementEA_demo.set).
