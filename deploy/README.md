# Déploiement du SIRH

Deux chemins sont fournis. **Suivez celui avec Coolify** : c'est celui qui a
été retenu, et Coolify est déjà installé sur le VPS.

- [Chemin A — avec Coolify](#chemin-a--avec-coolify) ← le vôtre
- [Chemin B — Docker Compose seul](#chemin-b--docker-compose-seul) (sans Coolify)

**Cible** : Ubuntu 24.04, 2 vCPU / 8 Go.
**Durée** : environ une heure la première fois.

---

## Ce qu'il faut avoir sous la main

1. L'accès à l'interface Coolify et au VPS en SSH.
2. Le **nom d'hôte public** du serveur : `hostname -f` en SSH. Le nom par
   défaut d'Hostinger (`srvXXXXXX.hstgr.cloud`) est un vrai nom DNS, Let's
   Encrypt sait lui délivrer un certificat — inutile d'acheter un domaine.
3. Deux mots de passe tirés au sort, générés sur votre poste :

   ```bash
   openssl rand -base64 36    # pour PostgreSQL
   openssl rand -base64 36    # pour le mot de passe maître d'Odoo
   ```

   Conservez-les dans votre gestionnaire de mots de passe. Ils ne seront
   écrits nulle part ailleurs.

---

# Chemin A — avec Coolify

## A1. Faire le ménage de l'instance de test

L'Odoo déployé pour la démonstration utilise l'**image officielle** : il ne
contient aucun module `villa_nova_*`, donc aucune de vos fonctionnalités.
Supprimez cette ressource dans Coolify avant de continuer, pour éviter toute
confusion entre les deux instances.

## A2. Créer la ressource

Dans Coolify : **+ New** → **Docker Compose** → dépôt Git.

| Champ | Valeur |
|---|---|
| Repository | l'URL de votre dépôt SIRH |
| Branch | `main` |
| Base Directory | `/` |
| Docker Compose Location | `/deploy/docker-compose.coolify.yml` |

Le dépôt étant privé, Coolify vous demandera une clé de déploiement :
ajoutez la clé publique qu'il affiche dans **Settings → Deploy keys** de votre
dépôt GitHub.

## A3. Renseigner les variables

Onglet **Environment Variables** :

```
POSTGRES_USER=odoo
POSTGRES_PASSWORD=<le premier mot de passe tiré au sort>
ODOO_ADMIN_PASSWD=<le second mot de passe tiré au sort>
```

Ces trois variables sont obligatoires : la pile refuse de démarrer sans elles,
volontairement. Un déploiement qui part avec `odoo/odoo` en mot de passe est
un déploiement qu'on oublie de corriger.

## A4. Déclarer le domaine

Onglet **Domains** du service `odoo` :

| Domaine | Port |
|---|---|
| `https://VOTRE_HOTE` | 8069 |
| `https://VOTRE_HOTE/websocket` | 8072 |

La seconde ligne est le bus temps réel. Sans elle, l'application fonctionne
normalement mais **les notifications en direct ne remontent jamais** — une
panne discrète, qui ne produit aucune erreur visible.

Le port 8072 n'existe que parce que `odoo.prod.conf` fixe `workers = 3`. En
mono-processus, tout passerait par 8069.

## A5. Déployer

**Deploy**. Le premier lancement construit l'image : comptez cinq à dix
minutes. Suivez les journaux dans Coolify.

À ce stade l'instance démarre avec une base **vide**. C'est normal : vos
données arrivent à l'étape suivante.

## A6. Transférer et restaurer vos données

Sur votre poste, dans Git Bash :

```bash
cd "/c/Users/kbrah/Desktop/LA BOITE A OUTILS/odoo18-hrms"
bash scripts/backup_sirh.sh                      # sauvegarde fraîche
scp backups/sirh_*.tar.gz root@VOTRE_IP:/tmp/
```

Une archive du SIRH pèse une trentaine de méga-octets.

Sur le serveur, repérez les noms de conteneurs créés par Coolify :

```bash
docker ps --format '{{.Names}}' | grep -Ei 'odoo|postgres'
```

Puis restaurez, en renseignant ces deux noms :

```bash
cd /tmp
SIRH_PG_CONTAINER=<nom-du-conteneur-postgres> \
SIRH_ODOO_CONTAINER=<nom-du-conteneur-odoo> \
bash /chemin/vers/deploy/restaurer_coolify.sh sirh_AAAAMMJJ_HHMMSS.tar.gz
```

Le script restaure la base **et** les pièces jointes. Restaurer la seule base
donne un SIRH dont tous les documents du personnel sont cassés, ce qui ne se
voit qu'en ouvrant un dossier.

Redémarrez ensuite le service depuis Coolify.

## A7. Vérifier

Dans l'ordre, sans en sauter :

| Vérification | Ce que ça prouve |
|---|---|
| `https://VOTRE_HOTE` s'ouvre, cadenas valide | Le proxy et le certificat fonctionnent |
| Connexion avec un compte existant | La base est restaurée |
| Une fiche employé affiche sa photo | Le filestore a suivi |
| Un rapport de présence se génère en PDF | wkhtmltopdf et les polices sont présents |
| Le chatter d'une tâche se met à jour sans rafraîchir | La route `/websocket` est bonne |
| `https://VOTRE_HOTE/web/database/manager` refuse l'accès | `list_db = False` est actif |

---

# Chemin B — Docker Compose seul

À n'utiliser que **sans** Coolify : la pile inclut son propre proxy Caddy, qui
entrerait en conflit avec Traefik sur les ports 80 et 443.

```bash
# 1. Préparer le serveur (Docker, compte de service, pare-feu, fail2ban)
ssh root@VOTRE_IP
git clone VOTRE_DEPOT /root/sirh && cd /root/sirh
bash deploy/bootstrap_vps.sh

# Vérifier depuis une SECONDE fenêtre, avant de fermer la session root :
ssh sirh@VOTRE_IP

# 2. Configurer (tire les secrets au sort, contrôle les verrous)
sudo -iu sirh
git clone VOTRE_DEPOT ~/sirh && cd ~/sirh
bash deploy/preparer_production.sh

# 3. Restaurer et démarrer
bash deploy/restaurer_sauvegarde.sh sirh_AAAAMMJJ_HHMMSS.tar.gz
```

---

# Sauvegardes automatiques

Quel que soit le chemin, ajoutez la sauvegarde au `cron` du serveur :

```cron
# Chaque nuit à 22 h 30, 7 jours conservés
30 22 * * * SIRH_PG_CONTAINER=<postgres> SIRH_ODOO_CONTAINER=<odoo> \
    /chemin/vers/scripts/backup_sirh.sh >> /var/log/sirh_backup.log 2>&1
```

**Une sauvegarde qui reste sur le serveur qu'elle protège ne protège de rien.**
Prévoyez une copie ailleurs — votre poste, le NAS du bureau via Tailscale, ou
un stockage objet. Et testez une restauration avant d'en avoir besoin.

---

# Exploitation courante

Avec Coolify, tout passe par l'interface : journaux, redémarrage, variables,
redéploiement après un `git push`.

En ligne de commande :

```bash
docker ps --format '{{.Names}}\t{{.Status}}'
docker logs -f <conteneur-odoo>

# Mettre à jour un module après modification du code
docker exec <conteneur-odoo> odoo -u villa_nova_project -d SIRH --stop-after-init --no-http
docker restart <conteneur-odoo>
```

**Un correctif Python n'est actif qu'après redémarrage du conteneur.**
`odoo -u` ne recharge que les vues et les données. Cette distinction a déjà
causé un incident en production : un correctif validé mais jamais chargé, et
43 employés déclarés absents le lendemain matin.

---

# Passer à un vrai domaine plus tard

Quand `sirh.infinity-africa.com` sera prêt :

1. Ajoutez un enregistrement DNS `A` vers l'IP du VPS.
2. Attendez que `dig +short sirh.infinity-africa.com` renvoie cette IP.
3. Dans Coolify, remplacez le domaine dans l'onglet **Domains** (les deux
   lignes, y compris `/websocket`) et redéployez.

Le certificat est obtenu automatiquement. L'ancien nom d'hôte cesse de
répondre : prévenez les utilisateurs avant.

---

# Si quelque chose ne va pas

**Le certificat n'est pas délivré.** Vérifiez que le nom d'hôte résout vers
l'IP du VPS (`dig +short VOTRE_HOTE`) et que les ports 80 et 443 sont
joignables. Let's Encrypt valide en appelant le port 80 : s'il est fermé,
rien ne peut aboutir.

**Odoo redémarre en boucle.** Lisez les journaux. Le plus souvent : mot de
passe PostgreSQL incohérent entre les variables Coolify et le volume déjà
créé, ou base absente.

**« ECHEC : le mot de passe maître n'a pas été injecté ».** `ODOO_ADMIN_PASSWD`
n'est pas défini dans Coolify. C'est un refus volontaire de démarrer plutôt
qu'un démarrage avec un mot de passe trivial.

**Les notifications en direct ne remontent pas.** La route `/websocket` vers
le port 8072 manque, ou `workers` est retombé à 0.

**Lenteurs.** Avec 2 vCPU, `workers = 3` est un plafond raisonnable ; au-delà
les processus se disputent le processeur au lieu de se répartir la charge.
