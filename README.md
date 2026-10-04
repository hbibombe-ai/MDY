# My Destiny — Suivi des chantiers

Application web de suivi des activités réalisées sur les chantiers de My Destiny : les équipes de terrain saisissent chaque jour ce qui a été fait, le conducteur de travaux valide, la direction suit l'avancement, les dépenses et les alertes sur un tableau de bord et une carte.

Écrite en Python avec [Streamlit](https://streamlit.io). Elle fonctionne sur ordinateur, tablette et téléphone, depuis un simple navigateur.

## Ce que fait l'application

| Page | Pour qui | Ce qu'on y fait |
| --- | --- | --- |
| Tableau de bord | Tous | Chantiers en cours et en retard, avancement réel comparé à l'avancement attendu, dépenses comparées au budget, alertes, carte, rapports reçus sur 30 jours |
| Carte | Tous | Chantiers colorés selon leur état, activités à réaliser, en cours ou réalisées ; filtres par chantier et par statut |
| Chantiers | Tous (création : direction) | Fiche de chaque chantier, coordonnées GPS, équipe affectée, modification, suppression |
| Activités | Tous (gestion : direction, conducteurs) | Tâches de chaque chantier, quantités prévues et réalisées, responsable, localisation |
| Rapport journalier | Chefs de chantier, conducteurs, direction | Quantité réalisée, effectif, dépenses, matériaux, incident, coordonnées GPS, photo |
| Validation | Conducteurs, direction | Validation groupée ou rejet motivé des rapports ; seuls les rapports validés comptent dans les indicateurs |
| Historique | Tous | Tous les rapports, filtres, photos, export Excel |
| Utilisateurs | Direction | Création des identifiants, rôles, chantiers affectés, réinitialisation des mots de passe, données de démonstration |
| Mon compte | Tous | Changement du mot de passe |

### Rôles

- **Administrateur (direction)** : voit tout, crée les chantiers et les comptes, valide les rapports.
- **Conducteur de travaux** : gère les activités et valide les rapports de ses chantiers.
- **Chef de chantier** : saisit les rapports journaliers de ses chantiers.
- **Lecteur** : consulte le tableau de bord et la carte, sans rien modifier.

Un conducteur ou un chef de chantier ne voit que les chantiers qui lui sont affectés.

### Sécurité des comptes

- Chaque usager a un identifiant personnel. L'administrateur crée le compte ; l'application génère un mot de passe provisoire, affiché une seule fois, que l'usager doit remplacer à sa première connexion.
- Les mots de passe sont chiffrés (PBKDF2-SHA256), jamais stockés en clair.
- Cinq erreurs de mot de passe bloquent le compte 15 minutes.
- La session reste ouverte 12 heures, même si la page est actualisée ; « Se déconnecter » la ferme sur tous les appareils.
- Un compte désactivé ne peut plus se connecter, mais son historique est conservé.

## Essayer en local

```bash
pip install -r requirements.txt
streamlit run app.py
```

À la première ouverture, connectez-vous avec l'identifiant **admin** et le mot de passe **changez-moi**, puis choisissez un mot de passe personnel. Dans la page **Utilisateurs**, le bouton **Charger les données de démonstration** crée cinq chantiers fictifs à Kinshasa, avec des activités, des rapports et des comptes de test (mot de passe `Demo2026`). Un clic sur **Supprimer les données de démonstration** les efface avant la mise en service réelle.

En local, les données sont enregistrées dans `donnees/suivi_chantiers.db` (SQLite).

## Mettre en ligne (gratuit)

L'hébergement proposé : **Streamlit Community Cloud** pour l'application et **Neon** (ou Supabase) pour la base de données PostgreSQL.

> Une base PostgreSQL est indispensable en ligne : sur Streamlit Community Cloud, le disque est effacé à chaque redémarrage, donc un fichier SQLite y perdrait toutes les données.

1. **Base de données.** Créez un compte sur [neon.tech](https://neon.tech), puis un projet. Copiez l'adresse de connexion (elle commence par `postgresql://`).
2. **Code.** Créez un dépôt GitHub **privé** et déposez-y tous les fichiers de ce dossier (sauf `donnees/` et `.streamlit/secrets.toml`).
3. **Application.** Sur [share.streamlit.io](https://share.streamlit.io), cliquez sur **Create app**, choisissez le dépôt et le fichier `app.py`.
4. **Secrets.** Dans **Advanced settings › Secrets** (ou plus tard dans **Settings › Secrets**), collez le contenu de `.streamlit/secrets.toml.example` en remplaçant les valeurs : nom de l'entreprise, devise, mot de passe initial de l'administrateur et adresse de la base Neon. Ajoutez aussi une ligne `CLE_SECRETE = "…"` avec une longue suite de caractères aléatoires.
5. **Déployer.** Ouvrez l'adresse de l'application, connectez-vous avec l'identifiant administrateur et le mot de passe initial des secrets, puis changez-le.
6. **Créer les comptes.** Dans **Utilisateurs**, créez un compte par personne et transmettez-lui son identifiant et son mot de passe provisoire.

Toute modification du code envoyée sur GitHub met l'application à jour automatiquement.

## Utiliser la carte

Chaque chantier et, si besoin, chaque activité (tronçon de route, forage, borne-fontaine…) peut recevoir des coordonnées GPS. Le plus simple : dans Google Maps sur le téléphone, appuyer longuement sur l'emplacement, copier les coordonnées affichées (par exemple `-4.3521, 15.3412`) et les coller dans le champ « Coordonnées GPS ». Un lien Google Maps fonctionne aussi.

Couleurs des chantiers : bleu = dans les délais, rouge = en retard, vert = terminé, gris = planifié, orange = suspendu. Un chantier est « en retard » quand son avancement réel est inférieur de plus de 15 points à l'avancement attendu à cette date, ou quand sa date de fin est dépassée.

## Fichiers

| Fichier | Rôle |
| --- | --- |
| `app.py` | Connexion, navigation selon le rôle |
| `auth.py` | Comptes, mots de passe, droits, session |
| `db.py` | Tables de la base de données (SQLite en local, PostgreSQL en ligne) |
| `calculs.py` | Avancement, état des chantiers, alertes |
| `ui.py` | Carte, coordonnées, photos, style My Destiny |
| `demo.py` | Données de démonstration |
| `vues/` | Une page par fichier |
| `static/` | Logo et icône My Destiny |
| `.streamlit/config.toml` | Couleurs et polices de la charte |

## Limites connues

- Les photos sont réduites (1 280 pixels, JPEG) et stockées dans la base : l'offre gratuite de Neon (0,5 Go) contient plusieurs milliers de photos ; au-delà, prévoir un stockage de fichiers dédié.
- L'application gratuite de Streamlit se met en veille après quelques jours sans visite ; le premier accès la réveille en une trentaine de secondes.
- La saisie demande une connexion internet au moment de l'envoi. Sur un chantier sans réseau, remplir le rapport puis l'envoyer dès que le réseau revient (ne pas fermer la page entre-temps).
