/**
 * Réception des photos de l'application d'enrôlement eAriary.
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
