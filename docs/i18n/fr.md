# Codex Quota Guard 0.5.0 : installation et utilisation

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
- « Surveille le quota de cette tâche toutes les 30 secondes. Préviens-moi à 82 % restants et, à 81 %, demande-moi si je veux la mettre en pause lorsqu’il restera 80 %. »
- « Arrête la surveillance du quota. »

Une consultation ponctuelle ne lance pas de vérifications périodiques. Avant de démarrer une surveillance continue, l’assistant hôte doit identifier la tâche précise, pouvoir exécuter la CLI dans une session supervisée en arrière-plan, traiter ses événements et garder la conversation disponible pour vos réponses. S’il ne peut pas remplir ces conditions, il doit expliquer cette limite et proposer uniquement une consultation ponctuelle, sans annoncer qu’une surveillance continue est active.

Depuis la racine du paquet :

```sh
# Consultation manuelle en français :
python3 scripts/quota_guard.py read --bucket codex --state-dir STATE --format text --locale fr
python3 scripts/quota_guard.py read --bucket codex --target 80 --task-key TASK --warn-margin 2 --confirm-margin 1 --state-dir STATE --format text --locale fr
# L’hôte doit superviser cette session en arrière-plan et traiter le JSON produit par défaut :
python3 scripts/quota_guard.py start --bucket codex --target 80 --task-key TASK --warn-margin 2 --confirm-margin 1 --interval 30 --state-dir STATE
# Depuis une autre session, avec le même répertoire d’état :
python3 scripts/quota_guard.py stop --state-dir STATE --format text --locale fr
```

Remplacez `TASK` par l’identité stable et vérifiée de la tâche précise à surveiller ; n’inventez pas d’identité et n’y incluez aucun secret. Le lien enregistré et émis utilise un hachage, jamais l’identifiant d’origine, et n’autorise pas le contrôle de la tâche. Remplacez `STATE` par le chemin absolu d’un répertoire privé (0700) appartenant à votre utilisateur, hors du dépôt et du cache du plugin, sous un répertoire parent de confiance accessible en écriture. N’utilisez pas `chmod` pour contourner les restrictions d’accès. Utilisez exactement le même répertoire pour l’arrêt. `codex` est un exemple de groupe de quota ; sélectionnez explicitement celui qui correspond à votre travail et utilisez des répertoires d’état distincts pour des groupes différents.

`start` reste un processus au premier plan, pas un service autonome : l’hôte doit conserver et superviser sa session en arrière-plan. Après la demande d’arrêt, vérifiez que le processus est terminé ; la demande seule ne le prouve pas. L’arrêt de la surveillance n’arrête pas la tâche observée.

## Objectif de quota restant et confirmation

`--target` accepte tout pourcentage fini de quota **restant** de 0 à 100 inclus, y compris des décimales comme `37.5`. Il ne désigne pas le pourcentage consommé. Les marges par défaut sont de 2 points de pourcentage pour l’avertissement et de 1 point pour la confirmation. Avec un objectif de 80 :
- À 82 % restants ou moins, l’événement `warning` est émis.
- À 81 % restants ou moins, l’événement `confirmation_required` est émis ; l’hôte doit demander, en identifiant la tâche : « Veux-tu que je mette cette tâche en pause lorsqu’il restera 80 % ? »
- À 80 % restants ou moins, l’événement `target_reached` est émis et l’admission de nouveaux travaux est refusée (`allow_new_work=false`). Cette décision coopérative d’admission ne met pas réellement la tâche en pause.

Les marges sont exprimées en points de pourcentage et acceptent des valeurs finies de 0 à 100 ; la marge d’avertissement doit être supérieure ou égale à celle de confirmation. Chaque seuil de déclenchement est plafonné à 100 %. Les marges ne déplacent pas le seuil d’admission : il reste exactement égal à l’objectif, avec un tampon effectif de 0.

Si la première mesure valide est déjà égale ou inférieure à l’objectif, l’hôte doit demander immédiatement : « Il reste déjà 80 % ou moins. Veux-tu mettre cette tâche en pause maintenant ? » Avec un objectif de 100, la question est immédiate même s’il reste 100 %. Un objectif de 0 ne garantit pas d’éviter l’épuisement du quota. Si plusieurs étapes se produisent lors d’une même mesure, regroupez-les dans un seul message, sans répéter la question.

Un événement ne prouve ni que l’utilisateur a été averti, ni qu’il a autorisé une action, ni que la tâche est en pause. L’hôte doit poser la question et vérifier la réponse réelle. Le silence ne vaut pas consentement. Toute action exige une autorisation explicite pour la tâche précise et un moyen de contrôle pris en charge et vérifié ; à défaut, il faut expliquer le blocage et demander une intervention manuelle de l’utilisateur. Il n’est pas permis de suspendre ou de terminer des tâches arbitraires. Vérifiez l’état réel de la tâche avant d’annoncer sa mise en pause ou son arrêt.

Une fois l’objectif atteint, le blocage d’admission persiste malgré une hausse ou une réinitialisation du quota, ainsi qu’après le redémarrage de la surveillance pour la même tâche et le même objectif. Aucun travail ne reprend automatiquement. Pour modifier la configuration, convenez des nouvelles valeurs, arrêtez la surveillance et vérifiez la fin du processus avant de la relancer. Utilisez `--new-cycle` seulement si l’utilisateur demande explicitement un nouveau cycle, après l’arrêt du précédent ; cela n’autorise ni pause ni reprise. Les événements sont enregistrés au plus une fois : si l’un d’eux est perdu, consultez l’état et l’historique réel de la conversation ; l’absence d’un nouvel événement ne prouve pas qu’une autorisation a déjà été demandée ou obtenue.

## Compatibilité avec le mode réserve

L’ancien mode `--reserve 10 --buffer 2` reste disponible uniquement comme option de compatibilité. Dans ce mode, la détection intervient à 12 % restants ou moins et ne garantit pas de conserver 10 %. Ne combinez pas `--target` avec `--reserve`, `--threshold` ou `--buffer` ; la CLI rejette ces combinaisons. Une ancienne réserve de 10 % ne remplace jamais l’objectif choisi, même s’il est inférieur à 10 %.

## Limites

Les vérifications périodiques peuvent détecter un franchissement trop tard ou manquer le pourcentage exact ; le retard des données et la consommation d’autres clients empêchent de garantir un arrêt exactement à l’objectif. Les données absentes, périmées, synthétiques ou invalides ne représentent pas un solde actuel et ne prouvent pas qu’un seuil est atteint ou franchi. Le plugin ne contrôle pas les tâches arbitraires dans le cloud. Son champ `checkpoint_status` reste toujours à `unconfirmed` ; seul l’orchestrateur responsable vérifie indépendamment les sauvegardes et la fin du travail. Une interruption gérée exige une autorisation explicite pour le fil et le tour exacts et accessibles. Une interruption confirmée ne confirme ni la fin de la tâche, ni la sauvegarde d’un point de reprise, ni la possibilité de reprendre le travail. Cet ancien mécanisme ne permet pas de contourner la confirmation du mode objectif ; `--target` rejette `--allow-interrupt`.

En savoir plus : [Contrat de confirmation de l’hôte (en anglais)](../CONFIRMATION-WORKFLOW.md) · [README](../../README.md) · [Langues](../LANGUAGES.md).


## Annonces publiques facultatives de Tibo

Dites «Surveille les annonces publiques de réinitialisation de Tibo chaque heure», «Préviens-moi seulement pour completed et banked en Asia/Shanghai», «Vérifie les annonces une seule fois» ou «Arrête les annonces publiques». La commande distincte `resetwatch` est utilisée. Une question signifie un seul `read` ; le démarrage exige une demande explicite de surveillance. L’hôte doit superviser le processus au premier plan, lire le JSON et utiliser son adaptateur local de notification existant. Sans ce canal, il doit indiquer que seule la sortie texte/JSON est disponible. L’installation ne démarre rien.

`planned` est un projet, pas une réalisation ; `completed` est le rapport tiers d’une annonce de réalisation ; `banked` est une réinitialisation stockée dont la réception et l’utilisation manuelle sont inconnues ; `manual_credit` annonce un crédit manuel dont il faut vérifier les conditions originales. Une annonce ne confirme pas votre quota, n’utilise aucun crédit et ne reprend/suspend pas automatiquement les recherches. Même «vérifié directement» reste une déclaration du fournisseur, pas une confirmation indépendante ni une API officielle.

Remplacez PUBLIC_STATE par un répertoire parent absolu privé hors dépôt/cache. `PUBLIC_STATE/public-reset-watch`, verrou et jeton d’arrêt sont distincts et ne modifient pas l’état du quota. La première récupération réussie crée silencieusement une référence. Les anciens messages, doublons, redémarrages et états anciens désordonnés ne répètent pas les alertes. Une évolution planned→completed ne peut émettre que le nouvel état. Changer les filtres ne rejoue pas l’historique. Arrêtez, vérifiez la fin du processus et redémarrez pour changer les réglages ; cela n’arrête ni recherches ni moniteur de quota.

`--events` sélectionne planned,completed,banked,manual_credit (tous par défaut). `--interval` : 3600..86400 secondes, 3600 par défaut. Le délai persiste après redémarrage ; le recul après erreur est limité à 24 heures. `--max-age` limite l’âge des éléments de récupération/contrôle en cache (172800 secondes, au moins l’intervalle et au plus 604800) ; `--event-age`, celui des nouvelles publications (604800, plage 3600..2592000). `--timeout` global : 1..30 secondes (10), avec au plus un délai de socket supplémentaire. `--timezone` utilise un fuseau IANA installé, UTC par défaut ; les dates machine restent UTC. `--locale` conserve les règles de repli ; champs et valeurs JSON ne sont pas traduits.

Par défaut, `--provider modelyard` lit seulement le RSS public fixe `/feed.xml`. HTML et les adresses arbitraires `--provider-url` ont été retirés ; changer de source exige un examen du code. Les catégories RSS sont des rapports tiers, pas une vérification officielle. `fetched_at` prouve une récupération locale ; lastBuildDate/dernière publication ne prouve pas la synchronisation. Un ancien feed valide peut créer la référence, avec couverture inconnue. Le périmètre suit le texte original fourni ou reste inconnu ; titre/contexte sont des déclarations du fournisseur. Les données limitées à ChatGPT ne sont pas envoyées comme Codex/Work. Un changement de catégorie du même message utilise `first_observed_status_at` et une évolution locale de l’agrégateur, sans date de modification inventée. Le callback utilise une voie locale existante de l’hôte ; livraison réelle non vérifiée. Réseau/téléchargement Library bloqués ici ; le premier élément réel découpé fourni directement est testé. Robots ne vaut pas autorisation de redistribution ; voir les sources.

Échec réseau/HTTP, contrôle périmé, format/dates invalides ou source falsifiée signifient inconnu, jamais «réinitialisé» ou «non réinitialisé» ; aucun événement n’est créé. Une consultation réussie sans nouvel événement ne prouve pas l’absence de réinitialisation. `status` est un cache, pas un nouveau contrôle ni une preuve d’activité du processus. Le registre est écrit avant sortie : une panne peut perdre la livraison et un événement ne prouve pas la notification. Veille, sortie et retards réseau/source interrompent la couverture. Ni garantie de temps réel ni démarrage automatique ; aucun nouveau compte, API payante, envoi de données personnelles ou nouvelle permission système de notification n’est requis.

```sh
python3 scripts/quota_guard.py resetwatch --help --locale fr
python3 scripts/quota_guard.py resetwatch read --state-dir PUBLIC_STATE --format text --locale fr
python3 scripts/quota_guard.py resetwatch start --state-dir PUBLIC_STATE --events completed,banked --interval 3600 --timezone Asia/Shanghai
python3 scripts/quota_guard.py resetwatch stop --state-dir PUBLIC_STATE --format text --locale fr
python3 scripts/quota_guard.py resetwatch status --state-dir PUBLIC_STATE --format text --locale fr
```

La surveillance publique requiert seulement Python/POSIX/réseau et les données IANA installées ; ni CLI officielle Codex ni compte ne sont nécessaires.

`--fixture FILE` est réservé à `read`, sans réseau/compte et avec état synthétique isolé ; une ancienne date est correctement signalée comme périmée.

[Contrat / JSON](../RESET-WATCH.md) · [Examen des sources](../RESET-SOURCES.md)
