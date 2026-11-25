// Page « Connecteurs et seuils » : état des connexions (source, LLM) et seuils de l'analyse.
// Les secrets (jeton Jira, clé LLM) ne s'affichent ni ne se modifient ici : ils vivent
// dans le fichier .env du serveur.
import { api, esc, nb } from "../outils.js";
import { relancer } from "../app.js";

/** Les seuils modifiables : [nom, libellé, explication, pas de saisie]. */
const CHAMPS = [
  ["taille_min_groupe", "Taille minimale d'un groupe", "Nombre minimal de tickets semblables pour former un groupe. 0 = automatique selon le volume (5 à 30).", 1],
  ["semaines_min", "Semaines minimales pour une récurrence", "Un problème est récurrent s'il apparaît dans au moins ce nombre de semaines.", 1],
  ["alpha", "Seuil de détection des pics (alpha)", "Probabilité sous laquelle un volume est jugé anormal. Plus petit = moins d'alertes.", 0.001],
  ["pic_min", "Tickets minimum pour un pic", "En dessous, une hausse est ignorée (trop petite pour agir).", 1],
  ["historique_pics", "Semaines d'historique avant de chercher des pics", "Le niveau habituel est estimé sur ces premières semaines.", 1],
  ["seuil_nouveaute", "Seuil de nouveauté", "Ressemblance minimale (0 à 1) pour rattacher un ticket à un problème connu. En dessous : nouveau problème.", 0.05],
  ["cohesion_min", "Cohésion minimale d'un groupe", "Ressemblance moyenne (0 à 1) entre un groupe et ses tickets. En dessous, le groupe est « à vérifier » (hétérogène).", 0.05],
  ["taux_pessimiste", "Gain — part évitée, scénario pessimiste", "Part des tickets évités si la cause est traitée (0 à 1).", 0.05],
  ["taux_median", "Gain — part évitée, scénario médian", "", 0.05],
  ["taux_optimiste", "Gain — part évitée, scénario optimiste", "", 0.05],
];

export async function afficher(zone, _parametre, etat) {
  const { valeurs, par_defaut } = await api("reglages");
  const s = etat.source, llm = etat.llm;
  const aide = { demo: "Jeu de démonstration (aucun identifiant requis).", fichier: "Fichier de tickets JSON ou CSV.",
                 jira: "API REST Jira, requêtes GET uniquement." }[s.type] || "";

  zone.innerHTML = `
    <div class="pile">
      <div class="grille g2">
        <div class="carte">
          <div class="titre-carte"><h2>Source des tickets</h2><span class="etiquette vert">lecture seule</span></div>
          <p><span class="point ${etat.erreur ? "rouge" : ""}"></span><strong>${esc(s.type)}</strong> — ${aide}</p>
          <p class="discret petit" style="word-break:break-all">${esc(s.detail)}</p>
          <p>${nb(s.nb_tickets)} tickets chargés${etat.date_analyse ? ` · analysés le ${esc(etat.date_analyse.replace("T", " à "))}` : ""}.</p>
          <p class="discret petit">Pour changer de source : variable <code>SOURCE</code> (demo, jira ou fichier) du fichier
            <code>.env</code>, puis redémarrer l'application. L'application ne modifie jamais Jira.</p>
          <div class="boutons"><button class="bouton" id="recharger-source">Relire la source et relancer l'analyse</button></div>
        </div>
        <div class="carte">
          <div class="titre-carte"><h2>LLM du copilote</h2>
            <span class="etiquette ${llm.actif ? "vert" : "gris"}">${llm.actif ? "configuré" : "non configuré"}</span></div>
          ${llm.actif
            ? `<p><span class="point"></span>Modèle : <strong>${esc(llm.modele)}</strong>. La clé est lue dans <code>.env</code> et n'est jamais affichée.</p>`
            : `<p><span class="point eteint"></span>Aucun LLM configuré : le chat est désactivé, tout le reste fonctionne.</p>
               <p class="discret petit">Pour l'activer : renseigner <code>AZURE_OPENAI_ENDPOINT</code>, <code>AZURE_OPENAI_KEY</code> et
                 <code>AZURE_OPENAI_DEPLOYMENT</code> dans <code>.env</code>, puis redémarrer.</p>`}
          <label style="display:flex;gap:8px;align-items:center;margin-top:8px">
            <input type="checkbox" id="nommage-llm" ${valeurs.nommage_llm ? "checked" : ""} ${llm.actif ? "" : "disabled"}>
            Laisser le LLM rédiger le nom précis et la description détaillée des problèmes</label>
          <p class="discret petit">Sans LLM (ou case décochée), le nom est le titre de ticket le plus représentatif et la
            description est assemblée par le moteur.</p>
        </div>
      </div>

      <div class="carte">
        <div class="titre-carte"><h2>Seuils de l'analyse</h2>
          <span class="discret petit">la semaine de référence et l'historique se choisissent en haut de page</span></div>
        <div class="formulaire">${CHAMPS.map(([nom, libelle, explication, pas]) => `
          <label>${libelle}<small>${explication} Valeur par défaut : ${String(par_defaut[nom]).replace(".", ",")}.</small>
            <input type="number" name="${nom}" value="${valeurs[nom]}" step="${pas}" min="0"></label>`).join("")}</div>
        <div class="boutons" style="margin-top:16px">
          <button class="bouton principal" id="enregistrer-seuils">Enregistrer et relancer l'analyse</button>
          <button class="bouton" id="seuils-defaut">Rétablir les valeurs par défaut</button></div>
        <p class="petit orange" id="erreur-seuils"></p>
      </div>
    </div>`;

  const erreur = document.getElementById("erreur-seuils");
  async function enregistrer(nouvelles) {
    erreur.textContent = "";
    try {
      await relancer(nouvelles);
    } catch (e) {
      erreur.textContent = "Valeur refusée : " + e.message;
    }
  }
  document.getElementById("enregistrer-seuils").addEventListener("click", () => {
    const nouvelles = { nommage_llm: document.getElementById("nommage-llm").checked };
    for (const [nom] of CHAMPS) nouvelles[nom] = Number(zone.querySelector(`[name=${nom}]`).value);
    enregistrer(nouvelles);
  });
  document.getElementById("seuils-defaut").addEventListener("click", () => {
    const nouvelles = {};
    for (const [nom] of CHAMPS) nouvelles[nom] = par_defaut[nom];
    enregistrer(nouvelles).then(() => afficher(zone, null, etat));
  });
  document.getElementById("recharger-source").addEventListener("click", () => relancer(null, true));
}
