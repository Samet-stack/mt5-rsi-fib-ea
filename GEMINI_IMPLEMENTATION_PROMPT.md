# Mission Gemini — implémenter un Expert Advisor MT5 robuste

Tu interviens comme collaborateur d’implémentation dans un périmètre strictement limité au projet :

```text
<PROJECT_ROOT>
```

Tu peux créer et modifier des fichiers uniquement sous ce répertoire. Ne lis ni ne transmets aucun secret, n’utilise aucun identifiant, ne contacte aucun service externe et n’exécute aucune action sur un compte de trading. Les captures sources, consultables uniquement si nécessaire, sont :

```text
<SCREENSHOT_1_PATH>
<SCREENSHOT_2_PATH>
<SCREENSHOT_3_PATH>
```

## Objectif

Créer une première version réellement compilable, testable et défensive d’un Expert Advisor MQL5 pour compte **démo**, fondé sur une sortie de zone RSI et une projection Fibonacci personnalisée. Le document normatif est :

```text
<PROJECT_ROOT>/docs/STRATEGY_SPEC.md
```

Lis-le intégralement avant de coder. En cas d’ambiguïté, choisis l’option la plus prudente, rends-la configurable et documente-la. Ne promets jamais une rentabilité et ne « sur-optimise » pas des valeurs sur les trois captures.

## Livrables obligatoires

1. `MQL5/Experts/RSIFibRetracementEA.mq5`
2. `README.md` en français : installation, paramètres, fonctionnement, backtest MT5, limites, procédure de passage démo et avertissement.
3. `presets/RSIFibRetracementEA_demo.set` avec valeurs prudentes.
4. `tests/test_strategy_math.py`, sans dépendance externe, qui vérifie les formules achat/vente, l’ordre relatif entrée/SL/TP et plusieurs cas limites purs.
5. `docs/IMPLEMENTATION_NOTES.md` listant les hypothèses, les protections et les éventuels éléments qui nécessitent encore une compilation MetaEditor.

Ne modifie pas `GEMINI_IMPLEMENTATION_PROMPT.md` ni `docs/STRATEGY_SPEC.md`.

## Exigences MQL5 non négociables

- `#property strict` et utilisation de la bibliothèque standard `Trade/Trade.mqh`.
- Indicateurs gérés par handles (`iRSI`, `iATR`) créés dans `OnInit`, vérifiés puis libérés dans `OnDeinit`.
- Signaux calculés uniquement avec `CopyBuffer` sur bougies clôturées (`shift 1` et `2`) ; aucune donnée future, aucun repaint.
- Détection fiable d’une nouvelle bougie sur le timeframe configuré. La logique de signal/ancrage ne doit pas se répéter à chaque tick.
- Machine d’états explicite : idle, attente d’ancrage, ordre pending, position. Re-synchronisation au démarrage avec les ordres/positions du même symbole et magic number.
- Formules symétriques achat/vente de la spécification. Inputs validés : `EntryRatio < 0`, `StopRatio < EntryRatio`, `TargetRatio >= 1`, seuil suracheté > seuil survendu, pourcentages et délais cohérents.
- Un `Buy Limit` seulement si le prix d’entrée est sous l’Ask ; un `Sell Limit` seulement s’il est au-dessus du Bid. Ne jamais remplacer automatiquement par un ordre au marché.
- Prix alignés sur `SYMBOL_TRADE_TICK_SIZE`, volumes alignés sur `SYMBOL_VOLUME_STEP`. Pour le volume, arrondir vers le bas afin de ne pas dépasser le risque.
- Taille de position par risque monétaire réel : equity × risque %, perte à 1 lot estimée en priorité par `OrderCalcProfit`, avec refus du trade si le calcul est impossible ou non fini.
- Validation des distances entrée/SL/TP par rapport à `SYMBOL_TRADE_STOPS_LEVEL` et au tick size avant envoi.
- Contrôle des retcodes `CTrade`, journal d’erreur explicite et aucune mutation d’état si l’opération broker échoue.
- SL et TP envoyés avec l’ordre pending ; commentaire court et stable ; magic number configurable.
- Ordre expiré/annulé après un nombre configurable de bougies, sur signal opposé, sur dépassement de l’invalidation ou lorsque les gardes de risque l’exigent.
- Garde compte démo activée par défaut. Si `DemoOnly=true` et que `ACCOUNT_TRADE_MODE` n’est pas `ACCOUNT_TRADE_MODE_DEMO`, `OnInit` doit échouer clairement.
- Interdiction totale de martingale, grid, moyenne à la baisse, doublement après perte ou empilement d’ordres.
- Compteurs journaliers calculés à partir de l’historique des deals du magic/symbole, avec profits, commissions et swaps. Plafond de drawdown journalier basé sur l’equity, de nouvelles entrées et de pertes consécutives.
- Filtre de spread configurable, filtre de session optionnel, contrôle `TerminalInfoInteger(TERMINAL_TRADE_ALLOWED)`, `MQLInfoInteger(MQL_TRADE_ALLOWED)` et mode de trading du symbole.
- Dessin optionnel des six niveaux (0, 1, entrée, stop, 2,56, 2,64), noms d’objets isolés par préfixe + magic + symbole. Nettoyer uniquement les objets de l’EA, jamais ceux de l’utilisateur.
- Le code doit fonctionner avec les symboles à suffixe et ne doit coder en dur ni `EURUSD`, ni l’or, ni un nombre de digits.
- Pas de DLL, pas de WebRequest, pas de dépendance tierce, pas de secret.

## Algorithme attendu pour l’ancrage

Après croisement RSI confirmé :

- conserver le temps/index logique de la bougie signal ;
- attendre au moins `MinImpulseBars` puis la première bougie opposée clôturée dans `AnchorWaitBars` ;
- achat : `P1 = highest High` sur la fenêtre signal→retracement, `P0 = Low` de la bougie baissière ;
- vente : `P1 = lowest Low` sur la fenêtre signal→retracement, `P0 = High` de la bougie haussière ;
- calculer le range et le filtrer avec ATR (`MinRangeATR` et `MaxRangeATR`, désactivables proprement) ;
- calculer entrée `-0.21`, stop/invalidation `-0.29`, TP `2.56`, seconde ligne visuelle `2.64`, tous configurables ;
- placer l’ordre limite seulement si toutes les contraintes sont satisfaites.

Fais très attention aux séries MQL5 (`ArraySetAsSeries`), aux shifts des bougies et aux différences netting/hedging. Ne prétends pas gérer une situation que le code ne traite pas réellement.

## Valeurs par défaut prudentes

- RSI 14, seuils 30/70, `PRICE_CLOSE`, timeframe courant ;
- risque 0,25 % d’equity par trade ;
- ratios `-0.21`, `-0.29`, `2.56`, `2.64` ;
- un seul ordre ou position ;
- 2 nouvelles positions maximum par jour ;
- 2 pertes consécutives maximum ;
- drawdown journalier maximum 1 % ;
- ordre valable 8 bougies ; signal/ancrage valable 8 bougies ;
- mode démo obligatoire ;
- visualisation et logs activés ;
- filtre horaire désactivé par défaut, car le symbole et le fuseau broker ne sont pas encore connus.

Pour le spread et les bornes ATR, choisis des valeurs portables ou un mode désactivé explicite ; n’invente pas une valeur universelle en points pour tous les symboles.

## Qualité et vérifications avant de terminer

- Relis le fichier MQL5 en entier après l’avoir écrit.
- Recherche les erreurs classiques : sélection d’ordre/position, enums incorrects, mauvais overload `CTrade`, sens des prix sell, off-by-one sur les shifts, division par zéro, NaN, arrondi du volume, jour broker, objets de graphique.
- Exécute `python3 -m unittest discover -s tests -v`.
- Si aucun compilateur MetaEditor n’est accessible, indique-le honnêtement dans les notes ; n’invente jamais un résultat de compilation.
- Termine par un résumé concis des fichiers créés, des tests exécutés et des risques résiduels.

Le résultat attendu n’est pas « le bot le plus rentable » sur le papier : c’est un EA propre, explicable, non trompeur et suffisamment instrumenté pour que Codex puisse ensuite le relire, le compiler, le backtester et l’améliorer sans risque caché.
