# Politique de sécurité

## Périmètre

RSIFibEA est un logiciel de recherche destiné exclusivement au Strategy Tester
et aux comptes MT5 démo. Il ne doit pas être utilisé pour piloter un compte
réel.

Les problèmes prioritaires sont notamment : contournement du garde démo,
dimensionnement supérieur au budget, ordre sans SL/TP, mauvaise restauration
après redémarrage, mutation d’une position étrangère, exposition de secrets ou
exécution inattendue de DLL/commandes externes.

## Signalement privé

Utilisez le formulaire privé GitHub :
[signaler une vulnérabilité](https://github.com/Samet-stack/mt5-rsi-fib-ea/security/advisories/new).

N’ouvrez pas d’issue publique contenant une clé, un identifiant de compte, un
rapport privé ou une procédure directement exploitable. Si le formulaire privé
n’est pas disponible, ouvrez seulement une issue indiquant qu’un contact privé
est nécessaire, sans détail sensible.

## Réponse attendue

Le mainteneur confirme la réception, reproduit en environnement démo/tester,
prépare un correctif avec test de non-régression, puis publie les détails après
mise à disposition du correctif. Aucun délai contractuel n’est garanti.
