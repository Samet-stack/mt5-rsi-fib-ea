# Patch de sécurité V3 — archive historique

État V3 vérifié le 5 août 2026. Ce document est un snapshot historique : le
source de recherche V4.2 a évolué depuis, notamment avec un plafond logiciel
de risque plus élevé pour le Strategy Tester. Les presets publics restent
bloqués par le gate de coûts. Ce patch ne valide pas la stratégie et
n'autorise aucun trading.

## Changements fail-closed

- Contexte strict : uniquement Strategy Tester ou compte classé démo, avec nouvelle vérification juste avant chaque mutation broker.
- Risque par trade plafonné à 0,25 %, valeur par défaut abaissée à 0,10 %.
- Vérification explicite du modèle de coûts obligatoire. Tous les presets gardent `InpCostModelVerified=false` et échouent donc à l'initialisation jusqu'à réception d'un barème broker vérifié. Un montant nul peut être déclaré uniquement si le broker confirme réellement zéro commission/frais.
- Sizing par `OrderCalcProfit` avec slippage adverse à l'entrée et au stop, coût par lot, contrôle après arrondi et refus si le budget est dépassé.
- `OrderCalcMargin` obligatoire ; une nouvelle position ne peut consommer plus de 25 % de la marge libre par défaut.
- Les ordres pending revérifient risque journalier, spread absolu, spread relatif au stop, session et cycle du contrat à chaque tick, puis demandent une annulation si une condition se dégrade.
- Pour un symbole à échéance, la durée pending complète doit finir strictement avant le cutoff `échéance − 7 jours` par défaut. Les modes d'expiration finis sont prioritaires et un future limité à GTC est refusé.
- Au cutoff, l'EA reste initialisé en mode gestion : il annule tout pending géré et demande la liquidation de toute position gérée, avec vérification des retcodes et retry sans effacer optimistement l'état broker. Un CFD sans date d'expiration n'est pas affecté.

Une course résiduelle existe entre un fill exécuté côté broker et la demande d'annulation envoyée par l'EA. Elle ne peut pas être supprimée par un contrôle `OnTick` et devra être incluse dans le stress de slippage/non-fill.
L'expiration serveur protège le pending si le terminal est hors ligne, mais aucune fermeture cliente d'une position ne peut être garantie lorsque MT5/VPS ou la connexion sont arrêtés ; le buffer de sept jours et les SL/TP broker restent donc obligatoires.

## Vérification

- Source historique V3 : `2d292e4074deeb1679d16fd2636e8cc01dd3aeb0e03ddca20ec13b249a8f445e`.
- Déploiement MT5 : hash identique.
- Compilation MetaEditor build 6090 : `0 errors, 0 warnings`, EX5 de 110 628 octets, SHA-256 `edf27c8a4e31ebb22dc6f8ad647d4eca4e9eeb54a72bfd03c26724cd860982c7`.
- Tests locaux : 111 réussis.
- Registre historique V3 : six événements valides, dernière empreinte `f0db7ae067edb62f7066cb6e12f37d6231cf839762540b93c4445d3d362b6f08`.
- Ordres envoyés pendant la sonde et les diagnostics : 0.

## Blocages maintenus

- CFD `XAUUSD` local contre future MGC visible dans les captures ;
- broker/serveur et symbole exacts non choisis ;
- commission/frais/slippage non fournis ;
- absence de ledger shadow MFE/MAE ;
- aucune puissance statistique ni holdout vierge.

Le bon comportement actuel est donc l'échec d'initialisation des presets et le maintien d'Algo Trading désactivé.
