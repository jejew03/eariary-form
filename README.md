# Formulaire d'enrôlement eAriary (Streamlit)

Formulaire mobile pour les agents de terrain. Chaque enregistrement ajoute une ligne
dans l'onglet **Journal** du Google Sheet « Onboarding marchand ». Le tableau de bord,
l'onglet Marchands et l'onglet À relancer se mettent à jour tout seuls.

## Ce que fait l'application

L'agent saisit uniquement **le nom du marchand**, **sa position** et **deux photos**.
La ligne du Journal reçoit la date du jour, l'agent, le canal `Descente`, le nom, la latitude,
la longitude, le résultat `Accepté` (pour être compté dans le tableau de bord) et les liens
des photos ; les autres colonnes (catégorie, ville, téléphone…) restent vides.

- **Position GPS automatique** : le bouton « Capturer ma position » lit le GPS du téléphone
  (haute précision) et affiche la latitude, la longitude, la précision en mètres et une carte.
  Une position hors de Madagascar (signe oublié, coordonnées inversées) est refusée.
  Saisie manuelle possible en secours. Les coordonnées s'affichent dans un cadre avec un bouton
  de copie (`-18.907597, 47.525359`, format accepté par Google Maps).
- **Photos** : une photo de la devanture et une photo des produits, prises avec l'appareil photo
  du téléphone (ou choisies dans la galerie). Elles sont redressées, réduites à 1600 px, envoyées
  dans un dossier Google Drive, et leurs liens sont écrits en colonnes Q et R du Journal.
- **Liste des agents** lue dans l'onglet Listes du Sheet. Ajouter un agent dans le Sheet suffit :
  l'application le reprend sous 10 minutes.
- **Contrôles avant écriture** : nom du marchand et position obligatoires ; photos facultatives.
- **Écriture sûre** : colonnes A à O et Q à R (jamais la colonne P calculée), après la dernière
  ligne remplie (même s'il y a des lignes vides au milieu), avec relecture pour éviter que deux
  agents écrasent la même ligne. Colonne Origine = `Streamlit`.
- **Récapitulatif du jour** de l'agent en bas de page.
- L'agent choisi est gardé dans l'adresse (`?agent=Aina`) : chaque agent peut enregistrer
  son propre lien en favori sur son téléphone.

## Mise en place (une seule fois, 15 minutes)

### 1. Créer un compte de service Google

1. Aller sur https://console.cloud.google.com, créer un projet (ex. `eariary-enrolement`).
2. *API et services > Bibliothèque* : activer **Google Sheets API**.
3. *API et services > Identifiants > Créer des identifiants > Compte de service*.
   Nom : `enrolement-eariary`. Pas de rôle nécessaire.
4. Ouvrir le compte créé > onglet *Clés* > *Ajouter une clé > JSON*. Un fichier `.json` est téléchargé.
   Il donne accès au Sheet : ne pas le partager ni le publier.

### 2. Partager le Google Sheet avec ce compte

Depuis le compte propriétaire du Sheet (`onboardingmarchand@gmail.com`) : *Partager*, coller
l'adresse `client_email` du fichier JSON (`...@...iam.gserviceaccount.com`), rôle **Éditeur**,
décocher « Envoyer une notification ». Dans *Accès général*, choisir **Restreint**.

### 2 bis. Photos (script Google)

Le compte propriétaire est un Gmail personnel, sans Drive partagé : un compte de service ne peut
pas y déposer de fichiers. Les photos passent donc par un petit script qui tourne avec les droits
du propriétaire et les range dans son Drive, dossier `eAriary - Photos enrôlement`.

1. Connecté en `onboardingmarchand@gmail.com`, ouvrir https://script.google.com > *Nouveau projet*,
   le nommer `eAriary photos`, remplacer le contenu par celui de `apps_script/Code.gs`, enregistrer.
2. *Paramètres du projet* (roue dentée) > *Propriétés du script* > ajouter `SECRET` avec la valeur
   de `photos_secret` (une longue chaîne aléatoire, la même dans les deux endroits).
3. Dans l'éditeur, choisir la fonction `initialiser` puis *Exécuter* et accepter les autorisations
   (« Google n'a pas validé cette application » : *Paramètres avancés > Accéder à eAriary photos*).
   Le dossier est créé dans le Drive.
4. *Déployer > Nouveau déploiement* > type **Application Web** ; *Exécuter en tant que* : **Moi** ;
   *Qui a accès* : **Tout le monde**. Copier l'URL qui finit par `/exec` dans `photos_url`.
5. Après une modification du script : *Déployer > Gérer les déploiements > Modifier > Nouvelle version*
   (l'URL reste la même).

« Tout le monde » est nécessaire pour que l'application puisse appeler le script ; le `SECRET`
empêche quiconque d'autre d'y déposer des fichiers. Les photos restent privées : pour que d'autres
personnes ouvrent les liens du Journal, partager le dossier avec elles dans Drive.

Sans `photos_url` / `photos_secret`, l'application fonctionne mais les champs photo sont désactivés.

### 2 ter. Formulaire des détails des marchands (facultatif)

L'application ne demande que le nom, la position et les photos. Le formulaire Google
« eAriary - Détails des marchands » permet de compléter ensuite la catégorie, la ville, le
téléphone, le contact, l'email et un commentaire. Il **met à jour la ligne existante** du
Journal (aucune ligne ajoutée) : le marchand reste compté une fois, les stats ne changent pas.
Parcours : on choisit d'abord l'**agent** (avec le nombre de fiches à compléter), puis l'un de
**ses** marchands enregistrés avec l'application dont la ville est vide, puis les détails.
Les agents viennent de l'onglet Listes (sans les « Équipe … »). Les listes se rechargent
**immédiatement** après chaque enregistrement dans l'application (l'application appelle le script,
action `maj`) et après chaque réponse au formulaire ; un rechargement toutes les 10 minutes
rattrape un éventuel appel manqué.

1. Dans le projet `eAriary photos` : *+ (Ajouter un fichier) > Script*, le nommer `Formulaire`,
   coller le contenu de `apps_script/Formulaire.gs`, enregistrer.
2. *Paramètres du projet > Propriétés du script* : ajouter `SHEET_ID` avec l'identifiant du
   Google Sheet (la partie de l'adresse entre `/d/` et `/edit`).
3. Choisir la fonction `creerFormulaire`, *Exécuter*, accepter les nouvelles autorisations.
4. Le journal d'exécution affiche le **lien à envoyer** aux personnes qui complètent les fiches,
   et le lien pour modifier le formulaire. Le formulaire est dans le Drive du propriétaire.

Après une modification de `Formulaire.gs` ou `Code.gs` : recoller le fichier, exécuter `majListes`
une fois, puis *Déployer > Gérer les déploiements > Modifier > Version : Nouvelle version > Déployer*
(sinon l'application web garde l'ancien code ; l'URL ne change pas).

Pas besoin de redéployer l'application web des photos : elle n'est pas concernée.

### 2 quater. Suivi des modifications du Journal

`apps_script/Modifications.gs` surveille les modifications faites à la main dans le Journal :

- un ancien contact (Refusé, À relancer, Injoignable… d'un jour précédent) passé à **Accepté** :
  l'ancienne ligne garde son résultat et une nouvelle ligne **datée du jour** est ajoutée
  (origine `Modification`). L'enrôlement compte le jour où il a eu lieu, pas à l'ancienne date ;
- le **nom du marchand remplacé** sur une ligne d'un jour précédent : le nom d'origine est remis
  et un message demande d'ajouter le nouveau marchand sur une nouvelle ligne.

Les lignes du jour se modifient librement. Installation : ajouter le fichier au projet
`eAriary photos`, puis exécuter `installerSuiviModifications` une fois.

### 3. Renseigner les secrets

Copier `.streamlit/secrets.toml.example` en `.streamlit/secrets.toml` et recopier les valeurs
du fichier JSON dans la section `[gcp_service_account]`. Garder les `\n` de `private_key`.

### 4. Déployer sur Streamlit Community Cloud (gratuit, HTTPS)

La géolocalisation des navigateurs ne fonctionne qu'en **HTTPS** : il faut donc un hébergement
HTTPS, pas un simple `http://adresse-ip:8501`.

1. Mettre ce dossier dans un dépôt GitHub **privé** (le `.gitignore` exclut déjà les secrets).
2. Sur https://share.streamlit.io : *Create app*, choisir le dépôt, fichier principal `app.py`.
3. *Advanced settings > Secrets* : coller tout le contenu de votre `secrets.toml`.
4. Déployer, puis envoyer le lien aux agents.

Pour restreindre l'accès : *Settings > Sharing* de l'application Streamlit, inviter les adresses
email des agents.

### 5. Carte des marchands onboardés (`carte.py`)

Carte de tous les marchands au statut final « Accepté » (onglet Marchands), aux couleurs du logo :
filtres par ville, catégorie, agent, canal et période, fiche du marchand avec ses photos au clic
sur un point ou une ligne du tableau. Les marchands sans position GPS restent dans le tableau.

- En local : `streamlit run carte.py`.
- En ligne : sur https://share.streamlit.io, une deuxième application sur le même dépôt, fichier
  principal `carte.py`, avec les mêmes secrets. Limiter l'accès (*Settings > Sharing*) aux
  personnes autorisées : la carte montre les téléphones des marchands.

Les photos restent privées dans le Drive. Pour que la carte les affiche, **partager le dossier
`eAriary - Photos enrôlement` en lecteur avec l'adresse du compte de service** (`client_email`
des secrets) : la carte les lit alors par l'API Drive. À défaut, elle passe par le script Google
(action `photo` de `apps_script/Code.gs`, après publication d'une nouvelle version), et en dernier
recours affiche un lien Drive à la place de chaque photo.

### Lancer en local (tests)

```bash
pip install -r requirements-dev.txt
streamlit run app.py          # http://localhost:8501 (la géolocalisation marche sur localhost)
python -m pytest -q tests     # 35 tests, sans connexion à Google
```

## Côté agent

1. Ouvrir le lien sur le téléphone, choisir son nom (une seule fois si le lien est mis en favori).
2. Devant le commerce : **Capturer ma position**, autoriser la localisation la première fois.
3. Saisir le nom du marchand, prendre les photos (devanture, produits), puis **Enregistrer**.

Si le navigateur a refusé la localisation : icône cadenas à gauche de l'adresse >
Autorisations > Position > Autoriser, puis recharger la page.

## Fichiers

| Fichier | Rôle |
|---|---|
| `app.py` | Interface Streamlit (formulaire des agents) |
| `carte.py` | Carte des marchands onboardés, avec leurs photos |
| `assets/logo-eariary.png` | Logo eAriary (recadré) |
| `sheets.py` | Lecture des listes, contrôles, écriture dans le Journal |
| `photos.py` | Compression des photos et envoi au script Google |
| `apps_script/Code.gs` | Script Google qui range les photos dans le Drive du propriétaire et les relit pour la carte |
| `apps_script/Formulaire.gs` | Formulaire Google pour compléter les détails des marchands |
| `apps_script/Modifications.gs` | Date du jour pour un ancien contact passé à « Accepté », anciennes lignes protégées |
| `tests/test_app.py` | Tests sur un faux Google Sheet (écriture, doublons, GPS, interface) |
| `.streamlit/secrets.toml.example` | Modèle des secrets |
