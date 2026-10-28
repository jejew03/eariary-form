/**
 * Suivi des modifications du Journal.
 *
 * 1. Un ancien contact passé à « Accepté » (Refusé, À relancer... d'un jour précédent) :
 *    l'ancienne ligne garde son résultat d'origine et une nouvelle ligne datée du jour est
 *    ajoutée avec « Accepté ». L'enrôlement compte donc le jour où il a eu lieu.
 * 2. Nom du marchand remplacé sur une ligne d'un jour précédent (réutiliser une vieille ligne
 *    pour un autre marchand) : le nom d'origine est remis et un message demande d'ajouter
 *    une nouvelle ligne.
 *
 * Installation : ajouter ce fichier au projet « eAriary photos » (propriété SHEET_ID déjà
 * créée pour Formulaire.gs), puis exécuter installerSuiviModifications() une fois.
 */
const COL_RESULTAT = 10;   // J
const COL_RAPPEL = 11;     // K
const ACCEPTE = 'Accepté';
const ORIGINE_MODIF = 'Modification';

/** À exécuter une seule fois. */
function installerSuiviModifications() {
  const deja = ScriptApp.getProjectTriggers().some(t => t.getHandlerFunction() === 'surModification');
  if (!deja) ScriptApp.newTrigger('surModification').forSpreadsheet(classeur()).onEdit().create();
  Logger.log(deja ? 'Suivi déjà installé.' : 'Suivi des modifications installé.');
}

/** Déclencheur « modification » du Google Sheet. */
function surModification(e) {
  const r = e.range;
  const feuille = r.getSheet();
  if (feuille.getName() !== 'Journal' || r.getRow() < 2 || r.getNumRows() !== 1 || r.getNumColumns() !== 1) return;
  const n = r.getRow();
  const ancien = e.oldValue === undefined ? '' : String(e.oldValue);
  const nouveau = e.value === undefined ? '' : String(e.value);
  if (ancien === nouveau) return;

  const ligne = feuille.getRange(n, 1, 1, COL.origine).getValues()[0];
  if (!jourPrecedent(ligne[COL.date - 1])) return;      // ligne du jour : modification libre

  if (r.getColumn() === COL.marchand && ancien.trim()) {
    r.setValue(texte(ancien));
    e.source.toast("Cette ligne est un contact d'un jour précédent : son marchand ne peut pas être "
                   + 'remplacé. Ajoutez le nouveau marchand sur une nouvelle ligne en bas du Journal.',
                   'Ligne protégée', 15);
    return;
  }

  if (r.getColumn() === COL_RESULTAT && nouveau === ACCEPTE && ancien !== ACCEPTE) {
    r.setValue(ancien);                                    // l'ancien contact reste tel quel
    const copie = ligne.slice();
    copie[COL.date - 1] = aujourdhui();
    copie[COL_RESULTAT - 1] = ACCEPTE;
    copie[COL_RAPPEL - 1] = '';
    copie[COL.origine - 1] = ORIGINE_MODIF;
    const libre = ajouterLigne(feuille, copie);
    e.source.toast('Enrôlement compté aujourd\'hui : nouvelle ligne ' + libre
                   + ' ajoutée, la ligne ' + n + ' garde son résultat du ' + dateTexte(ligne[COL.date - 1]) + '.',
                   'Accepté', 10);
  }
}

// ------------------------------------------------------------------ utilitaires

function aujourdhui() {
  return Utilities.formatDate(new Date(), TZ, 'dd/MM/yyyy');
}

function dateTexte(d) {
  return d instanceof Date ? Utilities.formatDate(d, TZ, 'dd/MM/yyyy') : String(d);
}

/** Vrai si la date de la ligne est antérieure à aujourd'hui (fuseau de Madagascar). */
function jourPrecedent(d) {
  if (!(d instanceof Date)) return false;
  return Utilities.formatDate(d, TZ, 'yyyy-MM-dd') < Utilities.formatDate(new Date(), TZ, 'yyyy-MM-dd');
}

/** Écrit la ligne après la dernière ligne ayant un marchand (comme l'application). */
function ajouterLigne(feuille, valeurs) {
  const verrou = LockService.getScriptLock();
  verrou.waitLock(30000);
  try {
    const colD = feuille.getRange(1, COL.marchand, feuille.getLastRow(), 1).getValues();
    let derniere = 1;
    colD.forEach((v, i) => { if (String(v[0]).trim()) derniere = i + 1; });
    const n = derniere + 1;
    const ecrites = valeurs.map((v, i) => (i === COL.date - 1 || v instanceof Date || typeof v === 'number') ? v : texte(v));
    ecrites[COL.telephone - 1] = valeurs[COL.telephone - 1] ? "'" + String(valeurs[COL.telephone - 1]).trim() : '';
    feuille.getRange(n, 1, 1, ecrites.length).setValues([ecrites]);
    return n;
  } finally {
    verrou.releaseLock();
  }
}
