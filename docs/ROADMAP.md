# Roadmap publique

Cette roadmap décrit l’ordre des travaux. Elle ne constitue pas un calendrier
de rendement et ne promet pas un commit quotidien.

## P0 — intégrité publique

- [x] garde tester/démo non contournable ;
- [x] tests Python et compilation MetaEditor séparés ;
- [x] registre expérimental append-only ;
- [x] retrait des chiffres V4 non accompagnés de rapports publics ;
- [x] documentation de contribution et de sécurité ;
- [ ] choix explicite de la licence par le propriétaire ;
- [ ] authentification GitHub rétablie et branche de préparation fusionnée.

## P1 — Gate marché et coûts

- [ ] choisir XAUUSD CFD ou MGC future ;
- [ ] figer broker, serveur, symbole et timeframe exacts ;
- [ ] archiver commission, spread, swap, slippage et règles de marge ;
- [ ] sonder le contrat cible sans envoyer d’ordre ;
- [x] mesurer la faisabilité du volume minimal sur MetaQuotes-Demo/XAUUSD :
  0,25 % est insuffisant sur janvier et 0,50 % ne permet que 0,01 lot ;

## P2 — qualité des données

- [ ] manifeste de ticks avec trous, timezone et DST ;
- [x] funnel journalisé signal/rejet/setup/ordre avec codes stables ;
- [ ] ledger complet fill/trade, MFE/MAE et motif de sortie ;
- [ ] MFE/MAE et temps vers les niveaux ;
- [ ] coûts et non-fills conservateurs ;
- [ ] séparation signal en R / contraintes du compte.

## P3 — validation

- [x] première ablation des sorties sur janvier 2026, désormais contaminé ;
- [ ] répéter les ablations sur des fenêtres préenregistrées non utilisées ;
- [ ] walk-forward préenregistré ;
- [ ] correction du nombre total d’essais ;
- [ ] holdout final réellement vierge ;
- [ ] forward démo seulement si tous les gates réussissent.

## Discipline continue

Chaque amélioration doit apporter au moins un élément vérifiable : test,
correctif, rapport brut, diagnostic, documentation d’un échec ou réduction
d’un risque. Réoptimiser les mêmes fenêtres sans nouvelle hypothèse ne compte
pas comme un progrès.
