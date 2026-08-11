# Calendrier économique déterministe dans Strategy Tester

Le calendrier économique live de MetaQuotes n'est pas utilisé dans le testeur.
La V4.30 exige un fichier explicite lorsque `InpNewsMode=2`.

## Emplacement

`InpTesterNewsFile` est un chemin relatif à `Terminal/Common/Files`, par
exemple :

```text
RSIFibEA\news_events_v1.csv
```

Les chemins absolus, `..` et les chemins contenant `:` sont refusés. Dans un
fichier `.set`, les chaînes ne doivent pas être entourées de guillemets.

## Schéma V1

Le séparateur est `;` et les timestamps sont en heure du serveur broker :

```csv
schema;RSIFIB_NEWS_V1;;
timezone;BROKER_SERVER;;
coverage_from;2026.01.01 00:00;;
coverage_to;2026.02.01 00:00;;
server_time;currency;importance;name
2026.01.07 14:30;USD;3;Identifiant ou nom de l'événement
```

Importance : `0` aucune, `1` faible, `2` modérée, `3` haute. Les événements
doivent être triés par timestamp, inclus dans la couverture et posséder une
devise et un nom non vides.

Le loader s'exécute une seule fois dans `OnInit`. Fichier absent, schéma
incorrect, timezone différente, couverture invalide, ligne malformée ou
recherche hors couverture entraînent un blocage fail-closed.

## Provenance et intégrité

Le format valide la structure, pas la véracité économique. Avant un backtest :

1. exporter depuis une source autorisée et traçable ;
2. convertir explicitement en heure serveur broker ;
3. conserver le fichier brut, sa provenance et son SHA-256 ;
4. archiver le fichier avec le run via
   `tools/archive_mt5_run.py --calendar-data <fichier>` ; le fichier est copié
   sous `inputs/news_events.csv` avec son SHA-256 et le rôle `calendar-data` ;
5. ne jamais compléter rétrospectivement les événements après observation du
   résultat.

Le fichier synthétique employé pour le test d'intégration V4.30 n'est pas une
source de données de marché et n'est volontairement pas livré comme dataset.
