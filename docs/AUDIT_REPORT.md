# Rapport de revue statique

## Résultat

La version `1.10` a été relue après la première implémentation Gemini. Les tests locaux Python passent, mais aucune compilation MetaEditor ni aucun backtest MT5 ne sont revendiqués : MetaEditor/MT5 n'a pas été trouvé dans la WSL ni dans les installations Windows détectables.

## Défauts critiques trouvés puis corrigés

- `OrderCalcProfit` recevait initialement `BUY_LIMIT/SELL_LIMIT`, alors que seuls `BUY/SELL` sont acceptés pour ce calcul. Sans correction, aucun lot ne pouvait être dimensionné.
- L'ordre pending retrouvé après redémarrage ne restaurait ni direction, ni heure, ni niveaux ; la géométrie et l'expiration sont maintenant reconstruites depuis les propriétés broker.
- Une suppression d'ordre échouée effaçait malgré tout l'état local ; le retcode est désormais obligatoire et l'annulation est retentée.
- Le volume était arrondi à deux décimales, ce qui pouvait dépasser le risque sur un symbole au pas `0,001`.
- Les statistiques comptaient les sorties comme nouvelles positions et ignoraient une partie des frais ; elles agrègent maintenant les fills par `DEAL_POSITION_ID`.
- Le drawdown journalier ignorait le PnL flottant ; la garde utilise maintenant le PnL réalisé net et flottant de l'EA.
- Le filtre ATR échouait ouvert ; il refuse maintenant le trade si l'indicateur demandé est indisponible.
- Le sens Bid/Ask de l'invalidation vendeur était incorrect.
- Un remplissage partiel pouvait laisser un reliquat pending ; l'EA tente désormais de supprimer le reliquat.
- La fermeture de sécurité réutilisait temporairement le filling `RETURN` des pendings, potentiellement invalide pour un ordre marché. Un second objet `CTrade` utilise désormais le filling marché du symbole.

## Références API vérifiées

- [`OrderCalcProfit`](https://www.mql5.com/en/book/automation/experts/experts_ordercalcprofit) : seuls les types marché `ORDER_TYPE_BUY` et `ORDER_TYPE_SELL` sont admis.
- [`CTrade::BuyLimit`](https://www.mql5.com/en/docs/standardlibrary/tradeclasses/ctrade/ctradebuylimit) : le booléen seul ne prouve pas l'acceptation serveur ; le retcode et le ticket sont vérifiés.
- [Types de filling](https://www.mql5.com/en/docs/constants/tradingconstants/orderproperties) : `ORDER_FILLING_RETURN` est prévu pour les ordres pending.
- [`OrderGetTicket`](https://www.mql5.com/en/docs/trading/ordergetticket) : sélection automatique de l'ordre avant lecture de ses propriétés.
- [Propriétés des deals](https://www.mql5.com/en/docs/constants/tradingconstants/dealproperties) : prise en compte de `DEAL_FEE`, `DEAL_POSITION_ID`, `IN`, `OUT`, `INOUT` et `OUT_BY`.

## Limites restantes

- Les ratios `−0,21`, `−0,29`, `2,56` et `2,64` proviennent de captures et doivent être confirmés statistiquement.
- La première bougie opposée est une formalisation nécessaire mais encore non validée par Samet sur un grand nombre d'exemples.
- L'equity de début de journée est estimée ; positions conservées depuis la veille et opérations externes au même compte peuvent la perturber.
- Un deal broker atypique portant le magic/symbole mais aucun `DEAL_POSITION_ID` bloque volontairement les nouvelles entrées jusqu'à ce que l'historique redevienne interprétable.
- Une collision manuelle de magic number créant plusieurs ordres simultanés n'est pas réparée automatiquement ; utiliser un magic unique par instance et vérifier le journal.
- Seule une compilation MetaEditor avec zéro erreur/avertissement, suivie de ticks réels et d'un forward test démo, permettra de qualifier l'EA pour exécution démo.
