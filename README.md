# Formulaire d'enrôlement eAriary (Streamlit)

Formulaire mobile pour les agents de terrain. Chaque enregistrement ajoute une ligne
dans l'onglet **Journal** du Google Sheet « Compte rendu _ Appel ». Le tableau de bord,
l'onglet Marchands et l'onglet À relancer se mettent à jour tout seuls.

## Ce que fait l'application

- **Position GPS automatique** : le bouton « Capturer ma position » lit le GPS du téléphone
  (haute précision) et affiche la latitude, la longitude, la précision en mètres et une carte.
  Une position hors de Madagascar (signe oublié, coordonnées inversées) est refusée.
  Saisie manuelle possible en secours.
- **Listes déroulantes** lues dans l'onglet Listes du Sheet (agents, catégories, villes, résultats).
  Ajouter une ville ou un agent dans le Sheet suffit : l'application le reprend sous 10 minutes.
- **Contrôles avant écriture** : champs obligatoires, téléphone à 9 chiffres (mis au format
  `+261 34 12 345 67`), email, position obligatoire en descente.
- **Détection des doublons** : même marchand dans la même ville ou même numéro. L'agent voit
  les lignes existantes et doit confirmer s'il s'agit d'une relance.
- **Écriture sûre** : colonnes A à O uniquement (jamais la colonne P calculée), après la dernière
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

Dans le Sheet : *Partager*, coller l'adresse `client_email` du fichier JSON
(`...@...iam.gserviceaccount.com`), rôle **Éditeur**, décocher « Envoyer une notification ».

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

### Lancer en local (tests)

```bash
pip install -r requirements-dev.txt
streamlit run app.py          # http://localhost:8501 (la géolocalisation marche sur localhost)
python -m pytest -q tests     # 20 tests, sans connexion à Google
```

## Côté agent

1. Ouvrir le lien sur le téléphone, choisir son nom (une seule fois si le lien est mis en favori).
2. Devant le commerce : **Capturer ma position**, autoriser la localisation la première fois.
3. Remplir le marchand, le téléphone, le résultat, puis **Enregistrer**.

Si le navigateur a refusé la localisation : icône cadenas à gauche de l'adresse >
Autorisations > Position > Autoriser, puis recharger la page.

## Fichiers

| Fichier | Rôle |
|---|---|
| `app.py` | Interface Streamlit |
| `sheets.py` | Lecture des listes, contrôles, écriture dans le Journal |
| `tests/test_app.py` | Tests sur un faux Google Sheet (écriture, doublons, GPS, interface) |
| `.streamlit/secrets.toml.example` | Modèle des secrets |
