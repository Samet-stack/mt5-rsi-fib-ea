# Contribuer à RSIFibEA

Merci de contribuer à ce projet de recherche. L’objectif est la
reproductibilité et la sécurité, pas la fabrication a posteriori d’une courbe
rentable.

## Règles non négociables

- Strategy Tester ou compte MT5 démo uniquement ; aucun chemin réel.
- Ne jamais contourner `InpDemoOnly` ou `InpCostModelVerified`.
- Aucun secret, identifiant de compte, cookie, token ou chemin personnel dans
  un commit, un rapport ou une issue.
- Aucun martingale, grid, averaging down ou augmentation automatique du risque
  après une perte.
- Une affirmation de performance doit être accompagnée des preuves brutes et
  doit préciser que les résultats passés ne garantissent rien.

## Installation développeur

```bash
git clone https://github.com/Samet-stack/mt5-rsi-fib-ea.git
cd mt5-rsi-fib-ea
python3 -m unittest discover -s tests -v
python3 tools/experiment_registry.py --root artifacts/experiments_v3 verify
```

La compilation MQL5 native nécessite MT5/MetaEditor sous Windows. Le script
`tools/deploy_compile_mt5.ps1` copie le source dans le dossier de données du
terminal associé, compile puis exige `0 errors, 0 warnings`.

Les anciens outils Python pilotant MT5 depuis WSL utilisent des variables
locales non versionnées :

```bash
export RSIFIB_MT5_DATA_DIR=/mnt/c/path/to/MetaQuotes/Terminal/<terminal-id>
export RSIFIB_MT5_CONFIG_DIR=/mnt/c/path/to/local/RSIFibEA
export RSIFIB_MT5_TERMINAL='/mnt/c/Program Files/MetaTrader 5/terminal64.exe'
```

Ne publiez jamais les valeurs propres à votre compte ou poste.

## Proposer une expérience

Avant le run, enregistrez : hypothèse causale, source/preset hashés, symbole,
serveur, dates, coûts, seed, métrique primaire, nombre de variantes et règle de
décision. Après le run, archivez le rapport brut même si le résultat est
négatif. Les fenêtres déjà consultées ne doivent pas être présentées comme un
holdout vierge.

## Pull request

1. créez une branche courte ;
2. limitez le diff à une hypothèse ou un correctif cohérent ;
3. ajoutez les tests de non-régression ;
4. lancez la suite Python et la compilation native si le MQL5 change ;
5. décrivez limites, coûts et risques résiduels ;
6. n’utilisez pas de vocabulaire promettant un gain.

Les noms historiques de presets peuvent être conservés pour la traçabilité,
mais la documentation nouvelle doit rester neutre.
