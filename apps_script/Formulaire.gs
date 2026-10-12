/**
 * Formulaire « eAriary - Détails des marchands ».
 *
 * Complète, dans le Journal, les lignes enregistrées avec l'application Streamlit
 * (nom, position, photos) : catégorie, ville, téléphone, contact, email, commentaire.
 * La ligne existante est mise à jour, aucune ligne n'est ajoutée : le marchand reste
 * compté une seule fois et les statistiques des agents ne bougent pas.
 *
 * Parcours : page 1 « Agent » -> page des marchands de cet agent -> page « Détails ».
 *
 * Installation : ajouter ce fichier au projet « eAriary photos », créer la propriété
 * du script SHEET_ID (identifiant du Google Sheet), puis exécuter creerFormulaire()
 * une fois (voir README, « Formulaire des détails »).
 */
const TZ = 'Indian/Antananarivo';
const ORIGINE_APP = 'Streamlit';
const AUCUN = '(aucun marchand à compléter)';
const Q = {
  agent: 'Agent',
  marchand: 'Marchand',
  categorie: 'Catégorie',
  ville: 'Ville',
  telephone: 'Téléphone',
  responsable: 'Responsable / contact',
  email: 'Email',
  commentaire: 'Commentaire',
};
// Colonnes du Journal (1 = A)
const COL = { date: 1, agent: 2, marchand: 4, categorie: 5, ville: 6, telephone: 7,
              responsable: 8, email: 9, commentaire: 12, origine: 15 };

/** À exécuter une seule fois : crée le formulaire et ses déclencheurs. */
function creerFormulaire() {
  const props = PropertiesService.getScriptProperties();
  if (props.getProperty('FORM_ID')) {
    const f = formulaire();
    Logger.log('Formulaire déjà créé.\nLien à envoyer : ' + f.getPublishedUrl() + '\nModifier : ' + f.getEditUrl());
    return;
  }
  const form = FormApp.create('eAriary - Détails des marchands');
  form.setDescription("Compléter les informations d'un marchand enregistré avec l'application "
                      + '(nom, position, photos). La liste se met à jour toutes les 10 minutes.');
  form.addListItem().setTitle(Q.categorie).setRequired(true);
  form.addMultipleChoiceItem().setTitle(Q.ville).showOtherOption(true).setRequired(true);
  form.addTextItem().setTitle(Q.telephone).setHelpText('Exemple : 034 12 345 67')
      .setValidation(FormApp.createTextValidation()
        .setHelpText('Numéro malgache : 9 chiffres après 0 ou +261')
        .requireTextMatchesPattern('[+0-9 .]{9,20}').build());
  form.addTextItem().setTitle(Q.responsable);
  form.addTextItem().setTitle(Q.email)
      .setValidation(FormApp.createTextValidation().requireTextIsEmail().build());
  form.addParagraphTextItem().setTitle(Q.commentaire);

  props.setProperty('FORM_ID', form.getId());
  ScriptApp.newTrigger('surReponse').forForm(form).onFormSubmit().create();
  ScriptApp.newTrigger('majListes').timeBased().everyMinutes(10).create();
  majListes();
  Logger.log('Lien à envoyer : ' + form.getPublishedUrl() + '\nModifier : ' + form.getEditUrl());
}

/**
 * Recharge les choix (agents, marchands à compléter par agent, catégories, villes)
 * et crée au besoin la question Agent, la page Détails et une page par agent.
 */
function majListes() {
  const verrou = LockService.getScriptLock();
  if (!verrou.tryLock(60000)) return;      // un autre rechargement est en cours
  try {
    majListesSansVerrou();
  } finally {
    verrou.releaseLock();
  }
}

function majListesSansVerrou() {
  const ss = classeur();
  const form = formulaire();
  const listes = ss.getSheetByName('Listes').getDataRange().getValues().slice(1);
  const colonne = c => [...new Set(listes.map(r => String(r[c]).trim()).filter(Boolean))];
  question(form, Q.categorie).asListItem().setChoiceValues(colonne(2));
  question(form, Q.ville).asMultipleChoiceItem().setChoiceValues(colonne(3));

  // Mêmes agents que l'application : les « Équipe ... » sont exclues
  const agents = colonne(0).filter(a => !a.startsWith('Équipe'));
  const parAgent = {};
  aCompleter(ss).forEach(l => { (parAgent[l.agent] = parAgent[l.agent] || []).push(l.libelle); });

  const s = structure(form, agents);
  agents.forEach(a => {
    const choix = parAgent[a] || [];
    s.pages[a].liste.setChoiceValues(choix.length ? choix : [AUCUN]);
  });
  s.agent.setChoices(agents.map(a => s.agent.createChoice(
    a + ' (' + (parAgent[a] || []).length + ' à compléter)', s.pages[a].saut)));
}

/**
 * Ordre des éléments : [Agent] [page agent 1] ... [page agent n] [page Détails : questions].
 * Chaque page d'agent renvoie vers la page Détails. Les identifiants sont gardés dans
 * les propriétés du script ; une ancienne version (une seule liste Marchand) est convertie.
 */
function structure(form, agents) {
  const props = PropertiesService.getScriptProperties();
  let agent = props.getProperty('AGENT_ID') && form.getItemById(Number(props.getProperty('AGENT_ID')));
  let details = props.getProperty('DETAILS_ID') && form.getItemById(Number(props.getProperty('DETAILS_ID')));
  const ids = JSON.parse(props.getProperty('PAGES') || '{}');

  if (!agent || !details) {
    // Conversion (reprend sans doublon ce qu'une exécution interrompue a déjà créé)
    const existant = (type, titre) => form.getItems(type).find(i => i.getTitle() === titre);
    form.getItems().filter(i => i.getTitle() === Q.marchand).forEach(i => form.deleteItem(i));
    details = existant(FormApp.ItemType.PAGE_BREAK, 'Détails du marchand')
        || form.addPageBreakItem().setTitle('Détails du marchand');
    deplacer(form, details, 0);
    agent = existant(FormApp.ItemType.LIST, Q.agent)
        || form.addListItem().setTitle(Q.agent).setRequired(true)
          .setHelpText("Choisissez l'agent qui a enregistré le marchand avec l'application.");
    deplacer(form, agent, 0);
    props.setProperty('AGENT_ID', String(agent.getId()));
    props.setProperty('DETAILS_ID', String(details.getId()));
  }
  // Relus par identifiant : un élément tout juste créé est déjà typé et n'a pas asListItem()
  agent = form.getItemById(Number(props.getProperty('AGENT_ID'))).asListItem();
  details = form.getItemById(Number(props.getProperty('DETAILS_ID'))).asPageBreakItem();

  const pages = {};
  Object.keys(ids).forEach(a => {               // pages d'agents retirés de Listes
    const saut = form.getItemById(ids[a][0]), liste = form.getItemById(ids[a][1]);
    if (!agents.includes(a) || !saut || !liste) {
      if (saut) form.deleteItem(saut);
      if (liste) form.deleteItem(liste);
      delete ids[a];
    } else {
      pages[a] = { saut: saut.asPageBreakItem(), liste: liste.asListItem() };
    }
  });
  agents.filter(a => !pages[a]).forEach(a => {  // nouveaux agents
    const saut = form.addPageBreakItem().setTitle('Marchands de ' + a);
    const liste = form.addListItem().setTitle(Q.marchand).setRequired(true)
        .setHelpText("Marchands enregistrés avec l'application dont la ville n'est pas encore renseignée.");
    deplacer(form, saut, details.getIndex());
    deplacer(form, liste, details.getIndex());
    pages[a] = { saut: saut, liste: liste };
    ids[a] = [saut.getId(), liste.getId()];
  });
  props.setProperty('PAGES', JSON.stringify(ids));

  // La page d'un agent se termine au saut de page suivant : on y indique « aller à Détails »
  const sauts = Object.values(pages).map(p => p.saut).sort((x, y) => x.getIndex() - y.getIndex());
  sauts.slice(1).forEach(sp => sp.setGoToPage(details));
  return { agent: agent, details: details, pages: pages };
}

/** Déclencheur : écrit la réponse dans la ligne du Journal du marchand choisi. */
function surReponse(e) {
  const verrou = LockService.getScriptLock();
  verrou.waitLock(30000);
  try {
    const rep = {};
    e.response.getItemResponses().forEach(ir => { rep[ir.getItem().getTitle()] = ir.getResponse(); });
    const choix = rep[Q.marchand];
    if (!choix || choix === AUCUN) return;

    const ss = classeur();
    const journal = ss.getSheetByName('Journal');
    const n = retrouverLigne(ss, journal, choix);
    if (!n) throw new Error('Marchand introuvable dans le Journal : ' + choix);

    const ecrire = (col, val) => { if (val) journal.getRange(n, col).setValue(texte(val)); };
    ecrire(COL.categorie, rep[Q.categorie]);
    ecrire(COL.ville, rep[Q.ville]);
    if (rep[Q.telephone]) journal.getRange(n, COL.telephone).setValue("'" + normaliserTelephone(rep[Q.telephone]));
    ecrire(COL.responsable, rep[Q.responsable]);
    ecrire(COL.email, rep[Q.email]);
    if (rep[Q.commentaire]) {
      const ancien = String(journal.getRange(n, COL.commentaire).getValue()).trim();
      ecrire(COL.commentaire, ancien ? ancien + ' | ' + rep[Q.commentaire] : rep[Q.commentaire]);
    }
  } finally {
    verrou.releaseLock();
  }
  majListes();
}

// ------------------------------------------------------------------ utilitaires

function classeur() {
  const id = PropertiesService.getScriptProperties().getProperty('SHEET_ID');
  if (!id) throw new Error('Propriété du script SHEET_ID manquante.');
  return SpreadsheetApp.openById(id);
}

/** Form.moveItem n'accepte pas un élément typé (PageBreakItem, ListItem) : on passe par les positions. */
function deplacer(form, element, position) {
  form.moveItem(element.getIndex(), position);
}

function formulaire() {
  return FormApp.openById(PropertiesService.getScriptProperties().getProperty('FORM_ID'));
}

function question(form, titre) {
  return form.getItems().find(i => i.getTitle() === titre);
}

/** Lignes de l'application dont la ville est vide. */
function aCompleter(ss) {
  const journal = ss.getSheetByName('Journal');
  const derniere = journal.getLastRow();
  if (derniere < 2) return [];
  const valeurs = journal.getRange(2, 1, derniere - 1, COL.origine).getValues();
  const out = [];
  valeurs.forEach((r, i) => {
    if (String(r[COL.marchand - 1]).trim() && !String(r[COL.ville - 1]).trim()
        && r[COL.origine - 1] === ORIGINE_APP) {
      out.push({ ligne: i + 2, agent: String(r[COL.agent - 1]).trim(), libelle: libelle(r, i + 2) });
    }
  });
  return out;
}

/** « Épicerie Fanja — Aina — 12/10 (ligne 512) » */
function libelle(r, n) {
  const d = r[COL.date - 1] instanceof Date
    ? Utilities.formatDate(r[COL.date - 1], TZ, 'dd/MM') : String(r[COL.date - 1]);
  return String(r[COL.marchand - 1]).trim() + ' — ' + r[COL.agent - 1] + ' — ' + d + ' (ligne ' + n + ')';
}

/** Numéro de ligne du choix, vérifié ; si la ligne a bougé (tri, suppression), on la recherche. */
function retrouverLigne(ss, journal, choix) {
  const m = /\(ligne (\d+)\)$/.exec(choix);
  if (m) {
    const n = Number(m[1]);
    const r = journal.getRange(n, 1, 1, COL.origine).getValues()[0];
    if (libelle(r, n) === choix) return n;
  }
  const sansLigne = s => s.replace(/ \(ligne \d+\)$/, '');
  const trouve = aCompleter(ss).find(l => sansLigne(l.libelle) === sansLigne(choix));
  return trouve ? trouve.ligne : null;
}

/** 034 12 345 67 / +261341234567 -> +261 34 12 345 67 (comme l'application). */
function normaliserTelephone(t) {
  let c = String(t).replace(/\D/g, '');
  if (c.startsWith('261')) c = c.slice(3);
  if (c.startsWith('0')) c = c.slice(1);
  if (c.length !== 9) return String(t).trim();
  return '+261 ' + c.slice(0, 2) + ' ' + c.slice(2, 4) + ' ' + c.slice(4, 7) + ' ' + c.slice(7);
}

/** Texte saisi : jamais interprété comme une formule. */
function texte(v) {
  const s = String(v).trim();
  return /^[=+\-@]/.test(s) ? "'" + s : s;
}
