# Plan d'expériences V3 — gelé au Gate 0

État : aucune expérience de sélection de paramètres n'est autorisée. Les deux seuls runs V3 exécutés sont des diagnostics de rapports historiques, pas des optimisations.

## Règles avant toute recherche

1. Résoudre `MGC future` contre `XAUUSD CFD`, broker/serveur, symbole exact et timeframe cible (`M15` reste à confirmer).
2. Refaire la sonde, établir les coûts et vérifier le risque minimal du compte 3 000 USD.
3. Construire un ledger de tous les setups, y compris les signaux rejetés, avec MFE/MAE, spread, slippage, temps vers fill et temps vers sortie.
4. Calculer et préenregistrer la puissance nécessaire. Le plancher logiciel de 100 trades est seulement un refus conservateur ; il ne constitue pas une preuve de puissance.
   Le seuil historique `InpTesterMinTrades=40` ne sert qu'au score `OnTester` et ne constitue aucun gate V3.
5. Geler code, preset, EX5, données, seed, métrique et critères avant le run.
6. Garder un holdout final sous contrôle d'un gardien OOS et ne l'ouvrir qu'une fois.

## Hypothèses causales candidates — maximum trois

Elles ne sont pas encore autorisées ; elles servent à cadrer la prochaine décision après Gate 0.

1. **Stop dans le bruit** : la distance structurelle actuelle est trop petite par rapport au spread et à la volatilité très courte. Une seule expérience comparera la géométrie actuelle à un stop structurel normalisé, sur le même ledger de setups et avant granularité de lot.
2. **Cible complète trop rare** : le retracement 2,56/2,64 produit une distribution jackpot. Une expérience testera une règle de sortie causale unique, sans changer simultanément entrée, stop et filtre.
3. **Réversion dépendante du régime** : la sortie RSI de survente/surachat n'a peut-être d'espérance que dans certains régimes de tendance/volatilité. Le filtre devra être défini à l'avance et évalué symétriquement long/short.

## Benchmarks et placebos obligatoires

- cash/no-trade ;
- RSI seul sans Fibonacci ;
- niveaux non-Fibonacci de complexité identique ;
- règle de tendance simple ;
- exposition passive à l'or ajustée au risque ;
- labels/signaux décalés comme placebo lorsque techniquement pertinent.

Chaque benchmark compte dans le budget total d'essais. L'usage de ratios Fibonacci doit battre les niveaux arbitraires après correction de sélection, pas seulement la baseline la plus faible.

## Protocole statistique

- Métrique primaire préenregistrée : espérance nette en R sur ledger commun, puis PnL réalisable après lot minimal, marge et coûts.
- Séries quotidiennes complètes, jours sans trade inclus.
- Intervalles par bootstrap en blocs avec sensibilités de longueur de bloc.
- Wilson ou méthode binomiale adaptée pour les TP rares.
- Concentration : résultat sans meilleur trade, top 5 %, long/short et régimes.
- Correction des essais multiples ; Deflated Sharpe/PBO uniquement si les hypothèses et le nombre de variantes le permettent. Référence méthodologique : [Bailey et López de Prado, Deflated Sharpe Ratio](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf).
- Stress coûts : spread, commission, frais, slippage, non-fill et délai, tous fondés sur le broker cible.

## Gates

- Gate 0 : identité marché/compte/coûts/granularité — **bloqué**.
- Gate 1 : intégrité des données et ledger shadow.
- Gate 2 : diagnostic causal et puissance.
- Gate 3 : développement walk-forward avec budget d'essais.
- Gate 4 : stress coûts et stabilité paramètres/régimes.
- Gate 5 : holdout vierge unique.
- Gate 6 : forward démo avec kill-switch ; jamais de passage live automatique.

Critère d'arrêt immédiat : coût non vérifié, résultat dépendant d'un gain, borne d'incertitude non positive, asymétrie inexpliquée, changement de contrat ou violation du registre.
