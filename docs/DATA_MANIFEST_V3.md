# Manifeste des données V3

Date du manifeste : 5 août 2026.

## Source observée

Les rapports proviennent de MT5 build 6090, `MetaQuotes-Demo`, broker affiché `MetaQuotes Ltd.`, devise USD, symbole `XAUUSD`, timeframe M15, dépôt 3 000 USD et levier 1:100. Ils servent uniquement de données de développement déjà contaminées. Ils ne représentent ni le broker final ni le future MGC montré sur les captures.

| Fenêtre demi-ouverte | Barres | Ticks | Qualité MT5 | Rôle autorisé |
|---|---:|---:|---|---|
| 2026-02-01 → 2026-05-01 | 5 683 | 43 836 815 | 100 % ticks réels | développement IS contaminé |
| 2026-05-01 → 2026-07-01 | 3 768 | 23 326 567 | 100 % ticks réels | validation temporelle déjà exposée |
| 2025-01-02 → 2026-01-01 | 23 547 | 29 616 721 | **0 % ticks réels** | invalide, interdit pour conclure |

Le libellé « OOS » du rapport mai–juin est historique. La fenêtre avait déjà été ouverte dans des rapports `PREOOS` ; elle n'est donc pas un holdout vierge. Son résultat négatif reste utile pour rejeter le candidat, mais aucun résultat positif futur ne pourra la transformer en preuve indépendante.

MetaTrader distingue les modes de génération et recommande le mode basé sur ticks réels lorsqu'il est disponible : [documentation MT5 sur la génération des ticks](https://www.metatrader5.com/en/terminal/help/algotrading/tick_generation).

## Artefacts figés

| Artefact | SHA-256 |
|---|---|
| Sonde `XAUUSD_MetaQuotes-Demo.json` | `49547647f882da13b8b5e7c07ef8e1bb555a433b16bcb70540c0847be96e0fbd` |
| Rapport IS candidat | `6fed745ee35482df250db34a676c611f97711218214bfa97c12f2c9652ffbe11` |
| Rapport mai–juin candidat | `0452516f5b1e887dca1486111aee504646c43ddffe7fc77f24f99338922f0eb5` |
| Diagnostic IS enregistré | `102f4d101fffcd5be4c8025468fc388224d5b633de73d5e4f91058bafaa7b55b` |
| Diagnostic mai–juin enregistré | `658591396bd43fc2c029ca3d2b9082c847058cb1f03a406539ebfe501b2b61b1` |

Le registre append-only est [ledger.jsonl](../artifacts/experiments_v3/ledger.jsonl). Il contient deux runs, six événements chaînés, des copies immuables des entrées et les diagnostics. Sa dernière chaîne vérifiée se termine par `f0db7ae067edb62f7066cb6e12f37d6231cf839762540b93c4445d3d362b6f08`.

## Limites et contrôles encore requis

- Commission affichée à zéro dans tous les deals ; aucun champ `fee` n'est exporté.
- Un swap total de -0,05 USD existe en IS ; les swaps ne sont donc pas tous nuls.
- Fuseau, DST, trous intraday, spreads par quantile et séquences Bid/Ask ne sont pas encore audités sur le broker cible.
- MFE/MAE par setup ne peuvent pas être reconstruits depuis les HTML.
- La sonde `OrderCalcProfit` est ponctuelle ; elle devra être répétée sur plusieurs prix et sur le contrat exact.
- Pour un future, les dates de début/échéance et la politique de roll deviennent obligatoires.

Toute nouvelle donnée devra être copiée dans un run immuable, hashée et associée à un rôle avant lecture du résultat.
