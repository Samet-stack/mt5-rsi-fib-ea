# Rapport d'audit V2

Date : 2026-08-04  
Périmètre : `RSIFibRetracementEA.mq5` v2.00, presets, tests et documentation.

## Résultat

La revue statique croisée Codex/Gemini et les audits indépendants ne laissent aucun bloqueur certain connu dans le source actuel. La suite locale compte **66 tests réussis sur 66** et chaque preset contient exactement les **54 inputs** déclarés par l'EA, sans manque ni nom inconnu.

Cette conclusion ne vaut pas compilation native : MetaEditor/MT5 n'est pas installé dans l'environnement WSL. Aucun `.ex5`, backtest en ticks réels ou forward test n'a donc été produit ici.

## Évolutions contrôlées

- filtres RSI quality, tendance MTF EMA/RSI et régime ATR, opt-in et fail-closed ;
- break-even Fibonacci monotone, aligné au tick et soumis aux contraintes broker ;
- restauration post-break-even depuis l'ordre limite historique (`POSITION_IDENTIFIER`, `DEAL_ORDER`, entrée/SL/TP), puis fallback entrée réelle + TP ;
- snapshot broker exhaustif, protection prioritaire, `STATE_FAULT` et suppression limitée au reliquat connu ;
- synchronisation coalescée par événement/nouvelle bougie/watchdog au lieu d'un scan à chaque tick ;
- cache des statistiques journalières invalidé uniquement par les deals ou le changement de journée ;
- paire RSI clôturée chargée en un seul `CopyBuffer` ;
- dashboard 1 Hz et fitness `OnTester` plafonné avec poids progressif jusqu'à l'échantillon cible ;
- manifeste IA compact et protocole delta-only pour réduire le contexte envoyé aux collaborateurs.

## Points contradictoires résolus

- Un premier audit Gemini a indiqué à tort que `HistoryDealGet*(ticket, property)` ne compilait pas. Les signatures officielles MQL5 confirment cette surcharge ; aucun changement incorrect n'a été appliqué.
- La restauration depuis le fill réel seul était sensible à une amélioration d'exécution. Elle privilégie maintenant les prix de l'ordre historique et conserve le fill réel uniquement pour le break-even.
- Le contrôle de protection est exécuté avant les retours `STATE_FAULT`, y compris quand plusieurs expositions rendent le snapshot ambigu.
- Le facteur de taille d'échantillon initial était constant après le seuil minimal. `InpTesterTargetTrades` rend désormais la pondération réellement progressive.

## Barrières restantes

Avant toute utilisation démo prolongée :

1. compiler dans MetaEditor avec 0 erreur et 0 avertissement ;
2. exécuter la golden trace avec tous les modules V2 désactivés ;
3. tester suppression de SL/TP, fill partiel, redémarrage après break-even, doublons et exposition étrangère ;
4. appliquer l'ablation, l'out-of-sample, le walk-forward et les coûts dégradés du protocole ;
5. conserver `InpDemoOnly=true`. Aucun passage en réel n'est validé ni recommandé par ce projet.
