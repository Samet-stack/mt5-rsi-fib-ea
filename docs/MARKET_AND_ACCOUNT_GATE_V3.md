# Gate 0 — marché, compte et granularité

Date de contrôle : 5 août 2026. État : **BLOQUÉ**.

Ce gate interdit toute optimisation et toute activation du robot. Il ne dit pas que la stratégie est mauvaise par définition ; il dit que l'instrument réellement disponible n'est pas encore celui que montrent les captures et que les coûts du broker cible ne sont pas connus.

## Faits observés

- Compte de test : 3 000 USD, levier 1:100, serveur `MetaQuotes-Demo`, société `MetaQuotes Ltd.`.
- Symbole disponible et sondé : `XAUUSD`, description `Gold vs US Dollar`, chemin `Metals\XAUUSD`.
- La sonde a été exécutée uniquement dans le Strategy Tester et indique `orders_sent=0`.
- `XAUUSD` local n'a ni date de début ni échéance : ce n'est pas le contrat future `MGCQ2026` visible dans les captures.
- Taille de contrat : 100 ; tick : 0,01 ; volume minimal/pas : 0,01.
- À la date du test : bid 4016,16, ask 4016,29, spread 0,13 et marge calculée d'environ 40,16 USD pour 0,01 lot. Ce sont des observations ponctuelles, pas un barème garanti.
- Swaps déclarés par la sonde en mode points : long -12,6 points, short -4,6 points, triple swap le mercredi. Leur conversion monétaire dépend du symbole et de la position. La commission et les autres frais du broker cible restent inconnus.
- La propriété MT5 `SYMBOL_TRADE_TICK_VALUE` retourne 0,10 USD, tandis que `OrderCalcProfit` implique 1,00 USD par tick et par lot. Le sizing doit donc utiliser `OrderCalcProfit` et refuser toute incohérence, jamais faire confiance au raccourci de valeur du tick.

Artefact : [XAUUSD_MetaQuotes-Demo.json](../artifacts/symbol-probe-2026-08-05/XAUUSD_MetaQuotes-Demo.json).

## Faisabilité du risque sur 3 000 USD

Le budget normal à 0,10 % vaut 3 USD ; le plafond absolu à 0,25 % vaut 7,50 USD.

Sur le `XAUUSD` sondé, 0,01 lot perd environ 1 USD par mouvement de prix de 1,00 avant commission, frais et slippage. Le stop brut maximal serait donc approximativement 3,00 de prix au risque normal, ou 7,50 au plafond. La distance réellement disponible doit être plus petite après coûts.

Pour le Micro Gold future CME, le contrat standard MGC représente 10 onces et son tick de 0,10 USD vaut 1 USD. Un budget brut de 3 USD ne couvre que trois ticks sur un contrat, avant frais et slippage. Ce calcul ne peut pas être transposé au CFD local. Référence produit : [CME Micro Gold](https://www.cmegroup.com/education/courses/understanding-micro-futures-contracts-at-cme-group/micro-gold-and-silver-futures/micro-gold-and-micro-silver-futures-product-overview).

## Éléments manquants

1. Choix explicite : `XAUUSD` CFD ou Micro Gold future MGC.
2. Broker et serveur démo cibles, puis symbole exact avec suffixe ou échéance.
3. Si MGC : cycle d'échéance, règle de roll, jours minimum avant expiry et horaires de maintenance.
4. Commission aller-retour, frais de deal/exchange, swap, spread par quantile et slippage observé.
5. Fuseau serveur et règle DST.
6. Nouvelle sonde sur ce symbole exact et historique Bid/Ask/Last vérifié.

## Décision

`GATE_0 = BLOCKED_MARKET_MISMATCH_AND_UNVERIFIED_COSTS`.

L'EA reste limité à la démo/testeur et ses presets sont maintenant bloqués par `InpCostModelVerified=false`. Algo Trading ne doit pas être activé. Aucun paramètre ne doit être choisi à partir d'un nouveau backtest avant la résolution de ce gate. Voir [SAFETY_PATCH_V3.md](SAFETY_PATCH_V3.md).
