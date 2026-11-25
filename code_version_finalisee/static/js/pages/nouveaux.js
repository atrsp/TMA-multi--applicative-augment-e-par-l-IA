// Page « Nouveaux tickets » : coller le texte d'un ticket pour savoir s'il correspond à un
// problème connu, et voir les derniers tickets de la semaine de référence déjà classés.
import { api, esc, nb, cle, jauge, etiquetteStatut, ATTENTE } from "../outils.js";
import { ticketEntrant } from "./tableau.js";

/** Affiche le verdict rendu par le moteur pour le texte collé. */
function verdict(r) {
  const p = r.probleme;
  const similaires = r.similaires.length ? `
    <h3 style="margin-top:14px">${r.connu ? "Tickets similaires déjà traités" : "Tickets les plus proches (ressemblance faible)"}</h3>
    <table><thead><tr><th>Clé</th><th>Titre</th><th>Application</th><th class="droite">Ressemblance</th></tr></thead>
      <tbody>${r.similaires.map(s => `<tr><td>${cle(s.cle)}</td><td>${esc(s.titre)}</td><td>${esc(s.application)}</td>
        <td class="droite chiffres">${nb(s.score, 2)}</td></tr>`).join("")}</tbody></table>` : "";

  if (!r.connu) {
    return `<div class="bandeau info"><div><strong>Nouveau problème.</strong> Aucun problème connu n'est assez proche
        (ressemblance ${nb(r.score, 2)}, seuil ${nb(r.seuil, 2)}) : à traiter normalement.
        ${p ? `Le plus proche : <a href="#/problemes/${p.id}">${esc(p.nom)}</a>.` : ""}</div></div>
      ${jauge(r.score, r.seuil)}${similaires}`;
  }
  return `<div class="bandeau ${p.statut === "a_verifier" ? "attention" : "pic"}"><div><strong>Problème connu :</strong>
      <a href="#/problemes/${p.id}">${esc(p.nom)}</a> ${etiquetteStatut(p.statut)} — ${nb(p.tickets)} tickets passés.</div></div>
    ${jauge(r.score, r.seuil)}
    <h3 style="margin-top:14px">Solution habituelle</h3>
    <p>${p.solution ? `${esc(p.solution)} <span class="discret">(notée dans ${p.solution_nb} ticket(s) sur ${p.tickets})</span>` : "Aucune résolution notée."}</p>
    ${similaires}`;
}

export async function afficher(zone) {
  const d = await api("nouveaux-tickets");
  zone.innerHTML = `
    <div class="grille g2" style="align-items:start">
      <div class="carte">
        <div class="titre-carte"><h2>Analyser un nouveau ticket</h2></div>
        <p class="discret">Collez le titre et la description d'un ticket. Le moteur le compare aux problèmes connus
          (calcul de ressemblance, sans LLM). Rien n'est envoyé à Jira.</p>
        <textarea id="texte-ticket" rows="5" placeholder="Ex. : Le batch de nuit a planté avec ORA-01555"></textarea>
        <div class="boutons"><button class="bouton principal" id="bouton-classer">Analyser</button>
          <button class="bouton" data-exemple="Le batch de nuit a planté avec ORA-01555">Exemple connu</button>
          <button class="bouton" data-exemple="Demande de devis pour une nouvelle imprimante">Exemple nouveau</button></div>
        <div id="verdict" style="margin-top:14px"></div>
      </div>
      <div class="carte">
        <div class="titre-carte"><h2>Derniers tickets de la semaine de référence</h2></div>
        ${d.tickets.length ? d.tickets.map(ticketEntrant).join("") : ATTENTE}
      </div>
    </div>`;

  const champ = document.getElementById("texte-ticket");
  const zoneVerdict = document.getElementById("verdict");
  async function classer() {
    if (champ.value.trim().length < 3) { zoneVerdict.innerHTML = '<p class="orange">Saisissez au moins quelques mots.</p>'; return; }
    zoneVerdict.innerHTML = '<p class="discret">Comparaison en cours…</p>';
    try {
      zoneVerdict.innerHTML = verdict(await api("nouveau-ticket", "POST", { texte: champ.value }));
    } catch (erreur) {
      zoneVerdict.innerHTML = `<p class="orange">${esc(erreur.message)}</p>`;
    }
  }
  document.getElementById("bouton-classer").addEventListener("click", classer);
  zone.querySelectorAll("[data-exemple]").forEach(b => b.addEventListener("click", () => { champ.value = b.dataset.exemple; classer(); }));
}
