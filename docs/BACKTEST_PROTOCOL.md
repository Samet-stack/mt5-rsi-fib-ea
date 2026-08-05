# Protocole de validation MT5

Ce protocole cherche à réfuter la stratégie avant de lui faire confiance. Trois captures gagnantes ne constituent pas un échantillon statistique.

## 1. Barrières techniques

1. Compiler dans MetaEditor avec **0 erreur et 0 avertissement**.
2. Utiliser uniquement le testeur **Every tick based on real ticks**.
3. Vérifier visuellement au moins vingt setups : croisement RSI, bougie opposée, P0/P1, entrée −0,21, stop −0,29 et cible 2,56.
4. Tester redémarrage/reconnexion avec un pending, expiration, suppression refusée, spread excessif et symbole dont le pas de volume vaut 0,001.
5. Tester explicitement : fill partiel, suppression manuelle du SL, SL déjà déplacé à break-even au redémarrage, doublon d'ordre, exposition étrangère et récupération depuis `STATE_FAULT`.

## 2. Données et coûts

- Tester le symbole et le timeframe réellement visés, avec le suffixe broker exact.
- Couvrir plusieurs régimes : tendance haussière, tendance baissière, range, volatilité forte et faible.
- Inclure spread variable, commission, swap et slippage. Refaire un scénario dégradé avec spread/slippage sensiblement supérieurs à l'historique moyen.
- Documenter tous les coûts du broker avant de passer `InpCostModelVerified=true`. `InpEstimatedRoundTurnCostPerLot=0.0` est admis seulement si l'absence de commission/frais est réellement confirmée ; spread et slippage restent obligatoires.
- Écarter les périodes ou symboles dont les ticks réels sont incomplets.

## 3. Séparation des données

1. Développement initial sur une période in-sample limitée.
2. Gel des règles avant d'ouvrir l'out-of-sample.
3. Validation sur une période out-of-sample chronologiquement postérieure.
4. Walk-forward roulant avec paramètres inchangés ou plages d'optimisation très étroites.

Les ratios issus des captures ne doivent pas être optimisés jusqu'à obtenir une belle courbe. Une zone voisine doit produire des résultats comparables ; un optimum isolé est un signal de surapprentissage.

## 3.1. Ablation V2 obligatoire

Comparer chronologiquement, avec mêmes données et mêmes coûts :

1. baseline V1 (tous les flags V2 à `false`) ;
2. qualité RSI seule ;
3. tendance MTF seule ;
4. régime ATR seul ;
5. break-even seul ;
6. combinaison complète.

Ne pas optimiser simultanément les ratios Fibonacci, les horaires, le risque et tous les filtres. Le critère `OnTester` sert à classer les candidats admissibles ; il ne remplace jamais l'out-of-sample. Exiger un plateau de paramètres voisin, plusieurs folds walk-forward positifs et refaire les scénarios avec coûts multipliés par 1,5.

## 4. Critères à examiner

- nombre de trades suffisant pour que quelques gagnants ne dominent pas tout le résultat ;
- profit factor et expectancy positifs **après tous les coûts** dans l'out-of-sample ;
- drawdown monétaire et en pourcentage compatible avec le risque prévu ;
- stabilité par année, régime et plage voisine de paramètres ;
- écart entre prix demandé et prix réellement exécuté ;
- taux de rejet lié au spread, au stops level et au volume minimum ;
- nombre de rejets par filtre V2 et stabilité de leur contribution dans chaque ablation ;
- séquences maximales de pertes et durée sans nouveau sommet d'equity.

Aucun seuil universel ne garantit une stratégie. Toute performance qui disparaît avec une légère hausse des coûts ou un petit déplacement des paramètres doit être rejetée.

## 5. Forward test démo

Après validation historique seulement :

1. garder `InpDemoOnly=true`, utiliser 0,10 % au départ et ne jamais dépasser le plafond logiciel de 0,25 % ;
2. utiliser un seul symbole/timeframe au départ ;
3. comparer chaque trade démo au journal et au backtest sur la même fenêtre ;
4. laisser tourner plusieurs semaines et obtenir un échantillon significatif avant toute nouvelle décision ;
5. arrêter immédiatement en cas d'ordre sans SL, de volume inattendu, de doublon ou d'écart inexpliqué entre niveaux calculés et niveaux broker.

Le Gate 0 actuel interdit ce forward tant que le marché et les coûts ne sont pas validés. Le passage en réel n'est pas inclus dans cette version du projet.
