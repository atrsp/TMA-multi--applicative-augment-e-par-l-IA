// =====================================================================================
// La carte d'un plan d'action, avec ses boutons Valider / Modifier / Rejeter.
// Utilisée dans la page « Plans d'action », dans le chat et dans la fiche d'un problème.
//
// Seul un clic humain sur ces boutons change le statut d'un plan : le copilote ne peut
// que proposer.
// =====================================================================================
import { api, esc, nb, cles, etiquettePlan } from "./outils.js";

/** Le texte du gain d'un plan (fourchette calculée par le moteur). */
function texteGain(plan) {
  if (!plan.gain) return "Gain non estimé (problème non récurrent)";
  return `Gain estimé : ${nb(plan.gain.pessimiste)} – ${nb(plan.gain.optimiste)} h/an (médian ${nb(plan.gain.median)} h)`;
}

/** Construit l'élément HTML d'un plan. `apresChangement` est appelée après chaque action. */
export function cartePlan(plan, apresChangement = () => {}) {
  const carte = document.createElement("div");
  carte.className = "plan " + plan.statut;

  const origine = plan.origine === "copilote" ? "proposé par le copilote" : "proposé par l'équipe";
  const lienProbleme = plan.probleme_id
    ? `<a href="#/problemes/${plan.probleme_id}">${esc(plan.probleme_nom)}</a>` : esc(plan.probleme_nom);
  const boutons = {
    propose: `<button class="bouton principal" data-action="valide">Valider le plan</button>
              <button class="bouton" data-action="modifier">Modifier</button>
              <button class="bouton danger" data-action="rejete">Rejeter</button>`,
    valide: `<button class="bouton" data-action="modifier">Modifier</button>
             <button class="bouton" data-action="propose">Remettre à valider</button>`,
    rejete: `<button class="bouton" data-action="propose">Remettre à valider</button>`,
  }[plan.statut];

  carte.innerHTML = `
    <div class="entete-plan">${etiquettePlan(plan.statut)} <strong>${esc(plan.titre)}</strong></div>
    <p class="petit discret">Problème : ${lienProbleme} · ${origine} le ${esc(plan.cree.slice(0, 10).split("-").reverse().join("/"))}</p>
    <ul>${plan.actions.map(a => `<li>${esc(a)}</li>`).join("")}</ul>
    <p class="petit discret">${texteGain(plan)} · ${nb(plan.nb_tickets)} tickets concernés · sources : ${cles(plan.tickets)}</p>
    ${plan.commentaire ? `<p class="petit"><strong>Commentaire :</strong> ${esc(plan.commentaire)}</p>` : ""}
    <div class="boutons">${boutons}</div>
    <div class="edition"></div>`;

  carte.querySelectorAll("[data-action]").forEach(bouton => bouton.addEventListener("click", async () => {
    const action = bouton.dataset.action;
    if (action === "modifier") return ouvrirEdition(carte, plan, apresChangement);
    const nouveau = await api("plans/" + plan.id, "PATCH", { statut: action });
    apresChangement(nouveau);
  }));
  return carte;
}

/** Affiche le petit formulaire de modification sous la carte. */
function ouvrirEdition(carte, plan, apresChangement) {
  const zone = carte.querySelector(".edition");
  zone.innerHTML = `
    <p class="petit fort" style="margin-top:12px">Titre</p>
    <input style="width:100%" name="titre" value="${esc(plan.titre)}">
    <p class="petit fort" style="margin-top:8px">Actions (une par ligne)</p>
    <textarea name="actions" rows="5">${esc(plan.actions.join("\n"))}</textarea>
    <p class="petit fort" style="margin-top:8px">Commentaire de l'équipe</p>
    <textarea name="commentaire" rows="2">${esc(plan.commentaire || "")}</textarea>
    <div class="boutons"><button class="bouton principal" data-enregistrer>Enregistrer</button>
      <button class="bouton" data-annuler>Annuler</button></div>
    <p class="petit orange" data-erreur></p>`;
  zone.querySelector("[data-annuler]").addEventListener("click", () => { zone.innerHTML = ""; });
  zone.querySelector("[data-enregistrer]").addEventListener("click", async () => {
    const actions = zone.querySelector("[name=actions]").value.split("\n").map(a => a.trim()).filter(Boolean);
    try {
      const nouveau = await api("plans/" + plan.id, "PATCH", {
        titre: zone.querySelector("[name=titre]").value.trim(), actions,
        commentaire: zone.querySelector("[name=commentaire]").value.trim(),
      });
      apresChangement(nouveau);
    } catch (erreur) {
      zone.querySelector("[data-erreur]").textContent = erreur.message;
    }
  });
}
