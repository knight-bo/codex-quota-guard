# Codex Quota Guard : installation et utilisation

Prérequis : Python 3.10 ou version ultérieure, un système POSIX et la CLI officielle Codex, authentifiée avec un compte admissible à la consultation du quota. Suivez la procédure habituelle d’autorisation et de connexion. Ne contournez ni les permissions ni l’authentification, ne modifiez pas `CODEX_HOME` pour éviter des restrictions et ne lisez pas directement les identifiants ou les fichiers de session.

## Installation

Exécutez :

```sh
codex plugin marketplace add knight-bo/codex-quota-guard
```

Redémarrez l’application de bureau, sélectionnez **Codex Quota Guard Local**, installez le plugin et activez-le. La publication sur GitHub ne vaut pas approbation dans le répertoire public des plugins. L’installation ne lance aucune surveillance et ne configure aucun démarrage automatique.

## Consulter, démarrer et arrêter

Exemples de demandes :
- « Consulte le quota Codex restant. »
- « Lance la surveillance avec une réserve de 10 %, une marge de 2 points de pourcentage et une vérification toutes les 30 secondes. »
- « Arrête la surveillance du quota. »

Une consultation ponctuelle ne lance pas de vérifications périodiques. Depuis la racine du paquet :

```sh
python3 scripts/quota_guard.py read --bucket codex --state-dir STATE --format text --locale fr
python3 scripts/quota_guard.py start --bucket codex --reserve 10 --buffer 2 --interval 30 --state-dir STATE --format text --locale fr
# Dans un autre terminal, pendant que start fonctionne au premier plan :
python3 scripts/quota_guard.py stop --state-dir STATE --format text --locale fr
```

Remplacez `STATE` par le chemin absolu d’un répertoire privé (0700) appartenant à votre utilisateur, hors du dépôt et du cache du plugin, sous un répertoire parent de confiance accessible en écriture. N’utilisez pas `chmod` pour contourner les restrictions d’accès. Utilisez exactement le même répertoire pour l’arrêt. `codex` est un exemple de groupe de quota ; sélectionnez explicitement celui qui correspond à votre travail.

`start` fonctionne au premier plan : surveillez sa session. Après la demande d’arrêt, vérifiez que le processus est terminé ; la demande seule ne le prouve pas.

## Limites

La détection intervient à 12 % restants ou moins : réserve de 10 % plus 2 points de marge. Elle ne garantit pas de conserver 10 %. D’autres clients peuvent consommer le quota. Les données périmées ou invalides ne représentent pas un solde actuel. Le plugin ne contrôle pas les tâches arbitraires dans le cloud. Son champ `checkpoint_status` reste toujours à `unconfirmed` ; seul l’orchestrateur responsable vérifie indépendamment les sauvegardes et la fin du travail. Une interruption gérée exige une autorisation explicite pour le fil et le tour exacts et accessibles. Une interruption confirmée ne confirme pas la fin de la tâche.

En savoir plus : [README](../../README.md) · [Langues](../LANGUAGES.md).
