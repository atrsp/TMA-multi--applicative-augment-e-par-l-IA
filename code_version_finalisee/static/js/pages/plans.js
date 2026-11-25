// Page « Plans d'action » : plans proposés, validés et rejetés. Seul l'humain décide.
import { api } from "../outils.js";
import { cartePlan } from "../carte_plan.js";
import { rafraichirEtat } from "../app.js";

let ongletActif = "propose";       // l'onglet affiché (gardé quand la page se redessine)

const ONGLETS = [["propose", "À valider"], ["valide", "Validés"], ["rejete", "Rejetés"]];

export async function afficher(zone) {
  const { plans } = await api("plans");
  const compte = statut => plans.filter(p => p.statut === statut).length;

  zone.innerHTML = `
    <p class="discret" style="margin-top:-8px">Le copilote et l'équipe peuvent <strong>proposer</strong> un plan.
      Seule l'équipe RUN peut le valider, le modifier ou le rejeter. Aucune action n'est exécutée automatiquement,
      et rien n'est écrit dans Jira.</p>
    <div class="onglets">${ONGLETS.map(([statut, titre]) =>
      `<button data-onglet="${statut}" class="${statut === ongletActif ? "actif" : ""}">${titre} (${compte(statut)})</button>`).join("")}</div>
    <div class="pile" id="liste-plans"></div>`;

  const liste = document.getElementById("liste-plans");
  const visibles = plans.filter(p => p.statut === ongletActif);
  if (!visibles.length) {
    liste.innerHTML = `<div class="carte"><p class="vide">Aucun plan dans cette liste. Demandez au copilote
      « Propose un plan d'action pour… », ou créez-en un depuis la fiche d'un problème.</p></div>`;
  }
  // Après chaque décision : mettre à jour le compteur du menu et redessiner la page.
  visibles.forEach(p => liste.appendChild(cartePlan(p, () => { rafraichirEtat(); afficher(zone); })));

  zone.querySelectorAll("[data-onglet]").forEach(b => b.addEventListener("click", () => {
    ongletActif = b.dataset.onglet;
    afficher(zone);
  }));
}
