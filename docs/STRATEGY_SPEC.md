# Spécification — RSI Fibonacci Limit EA

## Statut de cette spécification

Cette version transforme les explications orales et les captures d’écran de Samet en règles déterministes testables. Les ratios visuellement déduits sont des valeurs par défaut configurables, pas des vérités cachées dans le code.

Le robot est destiné d’abord et uniquement à un compte MetaTrader 5 de démonstration. Il n’existe aucune garantie de rentabilité. Une optimisation ne vaut rien sans validation hors échantillon, coûts réalistes et tests sur plusieurs régimes de marché.

## Intuition de la stratégie

- **Sous-évaluation** : le RSI a été inférieur ou égal à 30 puis clôture au-dessus de 30. La pression vendeuse pourrait s’épuiser ; on prépare uniquement un scénario acheteur.
- **Surévaluation** : le RSI a été supérieur ou égal à 70 puis clôture sous 70. La pression acheteuse pourrait s’épuiser ; on prépare uniquement un scénario vendeur.
- Après la sortie de zone RSI, on mesure un rebond et sa première bougie de retracement opposée.
- L’ordre limite est placé sur la ligne intermédiaire sous le niveau 0 du Fibonacci personnalisé.
- Si le prix retrace jusqu’à la ligne d’invalidation plus éloignée, le scénario est mort.
- La cible se situe dans la zone d’extension 2,56–2,64.

## Déclencheurs RSI

Toutes les décisions utilisent des bougies clôturées afin d’éviter le repaint intrabar.

### Achat

Sur deux bougies clôturées consécutives :

```text
RSI[2] <= OversoldLevel (30 par défaut)
RSI[1] >  OversoldLevel
```

### Vente

```text
RSI[2] >= OverboughtLevel (70 par défaut)
RSI[1] <  OverboughtLevel
```

Les paramètres par défaut sont RSI(14), prix de clôture, timeframe du graphique. Ils doivent être exposés comme inputs.

## Construction déterministe des ancrages

La lecture des captures implique la règle suivante, rendue configurable :

1. Lorsqu’un signal RSI est confirmé, enregistrer sa direction et son heure.
2. Attendre au moins une bougie d’impulsion, puis la première bougie clôturée de couleur opposée :
   - achat : première bougie baissière (`Close < Open`) ;
   - vente : première bougie haussière (`Close > Open`).
3. Achat :
   - `P1` (niveau 1) = plus haut atteint depuis la bougie du signal jusqu’à la bougie de retracement incluse ;
   - `P0` (niveau 0) = plus bas de la bougie baissière de retracement (mèche comprise).
4. Vente, symétriquement :
   - `P1` = plus bas atteint depuis la bougie du signal jusqu’à la bougie de retracement incluse ;
   - `P0` = plus haut de la bougie haussière de retracement (mèche comprise).
5. Rejeter une structure nulle, trop petite pour les contraintes broker, ou hors des bornes ATR configurées.
6. Si aucune bougie admissible n’apparaît avant `AnchorWaitBars`, expirer le signal.

## Géométrie Fibonacci personnalisée

Pour l’achat, avec `R = P1 - P0 > 0` :

```text
Price(ratio) = P0 + ratio * R
```

Pour la vente, avec `R = P0 - P1 > 0` :

```text
Price(ratio) = P0 - ratio * R
```

Ratios par défaut déduits des captures :

- entrée limite : `-0.21` ;
- invalidation / stop-loss : `-0.29` ;
- première borne de cible : `2.56` ;
- deuxième borne visuelle : `2.64`.

L’EA place par défaut son TP à 2,56, la borne prudente de la zone. Les quatre ratios sont des inputs validés au démarrage. Pour un achat, le stop doit être sous l’entrée et le TP au-dessus ; pour une vente, l’inverse.

## Cycle de vie d’un setup

États logiques :

```text
IDLE -> WAITING_FOR_ANCHOR -> PENDING_ORDER -> IN_POSITION -> IDLE
```

Un setup est annulé si l’une des conditions suivantes survient :

- signal RSI opposé ;
- délai d’ancrage ou d’ordre dépassé ;
- prix déjà au-delà de l’invalidation avant placement ;
- ordre devenu impossible à placer comme Limit (jamais de conversion silencieuse en ordre au marché) ;
- spread, distance minimale, volume ou garde-risque invalides ;
- perte journalière, nombre de trades ou série de pertes au-dessus des plafonds ;
- présence d’un ordre ou d’une position appartenant déjà à cet EA sur le symbole.

Après exécution, le SL broker est placé au niveau d’invalidation et le TP broker à 2,56. Aucun martingale, grid, ajout à une position perdante ou récupération de pertes n’est autorisé.

## Gestion du risque et sécurité

- Risque par trade calculé depuis l’equity et la perte estimée à 1 lot entre entrée et stop via `OrderCalcProfit` ; défaut : 0,25 %.
- Volume normalisé selon `SYMBOL_VOLUME_MIN`, `MAX` et `STEP`, sans arrondir au-dessus du risque voulu.
- Un seul setup/ordre/position par symbole et magic number.
- Plafond de perte journalière, nombre maximal de nouvelles positions par jour et série maximale de pertes.
- Filtre de spread, plage horaire optionnelle et délai d’expiration en bougies.
- Vérification de `SYMBOL_TRADE_STOPS_LEVEL`, du tick size, des permissions de trading et du retcode de chaque opération.
- Garde **compte démo uniquement**, activée par défaut et bloquante sur compte réel.
- Tous les filtres refusent proprement le trade ; ils ne doivent jamais augmenter le risque pour forcer une exécution.

## Affichage et diagnostic

L’EA dessine des lignes préfixées par son magic number pour : niveau 0, niveau 1, entrée, invalidation, cible 2,56 et borne 2,64. Il journalise les transitions d’état, les motifs de rejet/annulation, les prix normalisés, le volume, le risque monétaire estimé et les retcodes broker.

## Hypothèses restant à valider par les backtests

- La ligne intermédiaire visible est interprétée comme `-0.21` et la ligne basse comme `-0.29`.
- Le « bas de la bougie blanche » est interprété comme son `Low`, mèche comprise.
- La première bougie opposée après le signal est utilisée pour rendre la règle automatique.
- Le TP exécutable est fixé à 2,56 ; 2,64 reste la seconde borne affichée.

Ces hypothèses doivent être optimisées avec prudence et surtout validées hors échantillon. Elles ne doivent pas être modifiées implicitement par le code.
