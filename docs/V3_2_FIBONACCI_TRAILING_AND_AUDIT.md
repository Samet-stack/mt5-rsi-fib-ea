# Rapport de Mise à Jour V3.2 — Trailing Stop Fibonacci & Audit de Stabilité

Date : 6 août 2026  
Statut : **Validé (113/113 tests unitaires passés)**  
Dépôt : [https://github.com/Samet-stack/mt5-rsi-fib-ea](https://github.com/Samet-stack/mt5-rsi-fib-ea)

---

## 1. Objectif de la version V3.2

L'objectif principal de cette mise à jour est d'augmenter le taux de réussite (*win rate*) et de sécuriser les gains latents grâce à une gestion active de position, tout en corrigeant 5 anomalies techniques identifiées lors de l'audit de code approfondi.

---

## 2. Nouveautés Majeures

### A. Trailing Stop Fibonacci Multi-Niveaux (`InpUseFibTrailingStop`)

Dans les versions précédentes, une fois entré en position, l'EA s'en remettait uniquement au Take-Profit cible (`2.56`) ou au Stop-Loss initial (`-0.29`), avec un simple Break-Even optionnel. Un mouvement haussier majeur atteignant par exemple Fib 1.618 pouvait se retourner et terminer à 0 ou en perte.

Le Trailing Stop Fibonacci introduit 5 paliers stricts et monotones :

| Niveau de prix actuel | Action sur le Stop-Loss | Rationale stratégique |
| :--- | :--- | :--- |
| **Fib 0.382** | Verrouillage au **Break-Even** (`Entry ± 1 tick`) | Le trade est neutralisé et ne peut plus générer de perte |
| **Fib 0.618** | Verrouillage au **Fib 0.000** (`P0`) | Sécurise le premier palier de retournement |
| **Fib 1.000** | Verrouillage au **Fib 0.382** | Sécurise un profit net de ~1.0R |
| **Fib 1.618** | Verrouillage au **Fib 1.000** | Sécurise un profit net de ~2.0R |
| **Fib 2.000** | Verrouillage au **Fib 1.618** | Sécurise un profit net de ~3.0R+ avant le TP final (2.56) |

#### Propriétés de sécurité intégrées :
- **Monotonie stricte :** Le Stop-Loss ne peut que se rapprocher du prix (devenir plus protecteur), jamais reculer.
- **Respect du Stop Level broker :** Vérification de la distance minimale imposée par le broker (`SYMBOL_TRADE_STOPS_LEVEL` et `SYMBOL_TRADE_FREEZE_LEVEL`) avant d'envoyer l'ordre de modification.
- **Tolérance au tick :** Évite les modifications répétées et inutiles si le SL est déjà au niveau souhaité.

---

### B. Corrections de Stabilité et Robustesse (5 Bugs Résolus)

1. **Race Condition d'Exécution Immédiate (`ExecutePendingOrder`) :**
   - *Anomalie :* Lorsqu'un ordre limite était exécuté instantanément au tick suivant, `m_trade.ResultOrder()` retournait `0` dans certains terminaux MT5, faisant basculer l'EA en `STATE_FAULT`.
   - *Correction :* Récupération automatique du ticket d'ordre et de position depuis l'historique des deals via `HistoryDealGetInteger` et `m_trade.ResultDeal()`.

2. **Fuite de Mémoire & Gestion des Handles Indicateurs (`ReleaseAllHandles`) :**
   - *Anomalie :* En cas d'échec d'un paramètre dans `OnInit`, certains handles déjà créés (`iMA`, `iRSI`, `iATR`) n'étaient pas libérés.
   - *Correction :* Création d'une routine centralisée `ReleaseAllHandles()` appelée systématiquement sur toute sortie d'erreur et dans `OnDeinit`.

3. **Gestion Propre des Ordres Résiduels (`SyncState`) :**
   - *Anomalie :* Si un ordre limite résiduel était présent en parallèle d'une position active, l'EA se verrouillait en erreur irrécupérable.
   - *Correction :* L'EA adopte le ticket résiduel et procède à sa suppression propre et contrôlée (`DeleteResidualOrder`).

4. **Optimisation des Réallocations Mémoire (`UpdateDailyStats`) :**
   - *Correction :* Ajout d'une réserve de capacité (`reserve = 64`) lors de l'appel `ArrayResize` pour éviter les allocations mémoire répétitives lors de la mise à jour des statistiques journalières.

5. **Sécurisation des Divisions par Zéro sur le Calcul de Volume :**
   - *Correction :* Contrôles préventifs sur `tick_value`, `tick_size` et distance de stop avant tout dimensionnement.

---

## 3. Presets Mis à Jour

- [`presets/RSIFibEA_adaptive_xau_m15.set`](../presets/RSIFibEA_adaptive_xau_m15.set) :
  - **Géométrie adaptative activée** (`InpUseAdaptiveSL=true`, `InpUseAdaptiveTP=true`)
  - **Trailing Stop Fibonacci activé** (`InpUseFibTrailingStop=true`)
  - **Filtres V2 activés** (Qualité RSI, Tendance MTF H1, Régime de volatilité ATR)
  - Timeframe : M15 / Symbole recommandé : XAUUSD
- Tous les presets existants (`_demo.set`, `_v2_research.set`, `_control_010.set`, etc.) incluent désormais le paramètre `InpUseFibTrailingStop=false` pour garantir une stricte rétrocompatibilité.

---

## 4. Résultats de la Suite de Tests

```bash
Ran 113 tests in 1.473s

OK
```

Tous les tests de stratégie mathématique, de géométrie Fibonacci, de trailing stop multi-paliers et de contrats de sécurité MQL5 sont au vert.
