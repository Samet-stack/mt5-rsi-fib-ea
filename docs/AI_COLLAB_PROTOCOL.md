# Protocole IA delta-only

## But

Réduire le contexte transmis à Codex ou Gemini tout en conservant les invariants nécessaires à une revue fiable. Les IA travaillent sur les fichiers locaux ; le source complet ne doit pas être recopié dans chaque prompt.

## Paquet de tâche minimal

Chaque intervention contient seulement :

1. objectif atomique ;
2. chemin absolu du projet ;
3. fichiers et fonctions autorisés ;
4. invariants à préserver ;
5. commande de test attendue ;
6. format de réponse demandé : résumé, constats avec lignes ou patch delta.

Exemple :

```text
Projet: /home/9lx7/mt5-rsi-fib-ea
Scope: MQL5/Experts/RSIFibRetracementEA.mq5
Fonctions: RestoreSetupGeometry, CheckAndApplyBreakEven
Invariants: demo-only; ratios V1 inchangés; aucun ordre marché d’entrée
Test: python3 -m unittest discover -s tests -v
Sortie: constats bloquants uniquement, avec numéros de ligne
```

## Règles d’économie de contexte

- Gemini reçoit le chemin exact et lit localement les fichiers nécessaires.
- Un audit utilise le mode lecture seule/plan.
- Une implémentation utilise un périmètre d’écriture limité au projet et à une liste de fichiers.
- Ne jamais renvoyer un fichier complet de plus de 200 lignes : utiliser un diff ou des fonctions ciblées.
- Ne pas répéter la spécification stable ; transmettre son chemin et son SHA-256.
- Après chaque lot : fournir seulement fichiers modifiés, tests, erreurs et risques résiduels.
- Les logs verbeux sont désactivés hors diagnostic ; les motifs machine restent courts et stables.
- Aucun secret, identifiant de compte, token, cookie ou donnée broker privée n’entre dans un paquet IA.

## Budgets recommandés

- Orientation/audit ciblé : manifeste + 1 à 3 fonctions.
- Implémentation : un composant cohérent par tour.
- Revue finale : hashes, liste des fonctions changées, sortie des tests et source lu directement sur disque.

Le script `tools/ai_context_manifest.py` produit le manifeste compact et des extraits bornés sans exposer de fichier extérieur au projet.
