/**
 * Réception des photos de l'application d'enrôlement eAriary, rechargement immédiat
 * du formulaire des détails (action « maj ») après chaque enregistrement dans l'application,
 * et lecture des photos pour la carte des marchands (action « photo »).
 *
 * À installer une seule fois depuis le compte propriétaire du Google Sheet
 * (voir README, « Photos »). Le script tourne avec les droits de ce compte :
 * les photos vont dans son Google Drive, dans le dossier DOSSIER.
 *
 * Propriété du script à créer (Paramètres du projet > Propriétés du script) :
 *   SECRET = la même valeur que photos_secret dans les secrets Streamlit
 */
const DOSSIER = 'eAriary - Photos enrôlement';

function doPost(e) {
  try {
    const req = JSON.parse(e.postData.contents);
    const secret = PropertiesService.getScriptProperties().getProperty('SECRET');
    if (!secret || req.secret !== secret) {
      return reponse({ ok: false, erreur: 'Accès refusé' });
    }
    if (req.action === 'maj') {          // appelé par l'application après chaque enregistrement
      majListes();                        // (Formulaire.gs)
      return reponse({ ok: true });
    }
    if (req.action === 'photo') {        // appelé par la carte des marchands (carte.py)
      const fichier = DriveApp.getFileById(req.id);
      // Seules les photos du dossier d'enrôlement sont lisibles par ce biais
      if (!fichier.getParents().hasNext() || fichier.getParents().next().getName() !== DOSSIER) {
        return reponse({ ok: false, erreur: 'Fichier hors du dossier des photos' });
      }
      return reponse({ ok: true, data: Utilities.base64Encode(fichier.getBlob().getBytes()) });
    }
    const contenu = Utilities.base64Decode(req.data);
    const fichier = dossier().createFile(Utilities.newBlob(contenu, 'image/jpeg', req.nom));
    return reponse({ ok: true, url: fichier.getUrl() });
  } catch (err) {
    return reponse({ ok: false, erreur: String(err) });
  }
}

function dossier() {
  const trouves = DriveApp.getFoldersByName(DOSSIER);
  return trouves.hasNext() ? trouves.next() : DriveApp.createFolder(DOSSIER);
}

function reponse(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}

/** À lancer une fois à la main : crée le dossier et déclenche la demande d'autorisation Drive. */
function initialiser() {
  Logger.log('Dossier prêt : ' + dossier().getUrl());
}
