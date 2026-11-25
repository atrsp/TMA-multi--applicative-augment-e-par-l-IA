// =====================================================================================
// Point d'entrée du frontend : navigation entre les pages, en-tête, suivi de l'analyse.
//
// La navigation utilise l'ancre de l'adresse : « #/problemes/3 » affiche la fiche du
// problème 3. Chaque page est un fichier de js/pages/ qui exporte une fonction afficher().
// =====================================================================================
import { api, esc, ouvrirTicket } from "./outils.js";
import * as tableau from "./pages/tableau.js";
import * as problemes from "./pages/problemes.js";
import * as pics from "./pages/pics.js";
import * as gain from "./pages/gain.js";
import * as nouveaux from "./pages/nouveaux.js";
import * as plans from "./pages/plans.js";
import * as synthese from "./pages/synthese.js";
import * as copilote from "./pages/copilote.js";
import * as reglages from "./pages/reglages.js";

const PAGES = {
  tableau: { titre: "Tableau de bord du RUN", module: tableau },
  problemes: { titre: "Problèmes récurrents", module: problemes },
  pics: { titre: "Pics et alertes", module: pics },
  gain: { titre: "Gain estimé", module: gain },
  nouveaux: { titre: "Nouveaux tickets", module: nouveaux },
  plans: { titre: "Plans d'action", module: plans },
  synthese: { titre: "Synthèse hebdomadaire", module: synthese },
  copilote: { titre: "Copilote RUN", module: copilote },
  reglages: { titre: "Connecteurs et seuils", module: reglages },
};

/** Le dernier état connu de l'application (source, LLM, semaine de référence...). */
export let etat = null;

// ------------------------------------------------------------------ navigation --------
/** Affiche la page correspondant à l'ancre de l'adresse. */
export async function afficherPage() {
  const [nom, parametre] = location.hash.replace(/^#\/?/, "").split("/");
  const page = PAGES[nom] || PAGES.tableau;
  document.getElementById("titre-page").textContent = page.titre;
  document.querySelectorAll(".menu nav a").forEach(lien =>
    lien.classList.toggle("actif", lien.dataset.page === (PAGES[nom] ? nom : "tableau")));
  const zone = document.getElementById("page");
  try {
    await page.module.afficher(zone, parametre, etat);
  } catch (erreur) {
    zone.innerHTML = `<div class="bandeau erreur"><div>${esc(erreur.message)}</div></div>`;
  }
}

// ------------------------------------------------------------------ en-tête -----------
/** Met à jour l'en-tête, le menu et le bandeau d'état d'après /api/etat. */
function afficherEtat() {
  const ref = etat.semaine_ref;
  document.getElementById("sous-titre").textContent = etat.pret && ref
    ? `Semaine de référence S${ref.numero} (${ref.libelle})${ref.complete ? "" : " — en cours"} · source : ${etat.source.type} · ${etat.source.nb_tickets} tickets`
    : "Première analyse en cours…";

  // Liste des semaines : « Automatique » = dernière semaine complète.
  const choix = document.getElementById("choix-semaine");
  const options = ['<option value="">Automatique (dernière complète)</option>']
    .concat([...etat.semaines_disponibles].reverse().map(s => {
      const [a, m, j] = s.lundi.split("-");
      return `<option value="${s.lundi}">S${s.numero} · sem. du ${j}/${m}/${a}${s.complete ? "" : " (en cours)"}</option>`;
    }));
  choix.innerHTML = options.join("");
  choix.value = etat.semaine_ref_auto || !ref ? "" : ref.lundi;
  document.getElementById("choix-fenetre").value = String(etat.fenetre_semaines);

  for (const nom of ["problemes", "pics", "plans"]) {
    document.getElementById("c-" + nom).textContent = etat.compteurs[nom] || "";
  }

  document.getElementById("pied-menu").innerHTML = `
    <p><span class="point ${etat.erreur ? "rouge" : ""}"></span>${esc(etat.source.type)} · lecture seule</p>
    <p>${etat.date_analyse ? "Analysé le " + esc(etat.date_analyse.replace("T", " à ").slice(0, 18)) : "Pas encore d'analyse"}</p>
    <p><span class="point ${etat.llm.actif ? "" : "eteint"}"></span>Copilote IA ${etat.llm.actif ? "actif" : "désactivé"}</p>
    <p>Analyses disponibles sans IA</p>`;

  let bandeau = "";
  if (etat.analyse_en_cours) {
    bandeau = `<div class="bandeau info"><span class="sablier"></span><div><strong>Analyse en cours</strong> — ${esc(etat.etape)}…</div></div>`;
  } else if (etat.erreur) {
    bandeau = `<div class="bandeau erreur"><div><strong>Attention</strong> — ${esc(etat.erreur)}</div></div>`;
  }
  bandeau += (etat.avertissements || []).map(a => `<div class="bandeau attention"><div>${esc(a)}</div></div>`).join("");
  document.getElementById("bandeau-etat").innerHTML = bandeau;
  document.getElementById("bouton-analyse").disabled = etat.analyse_en_cours;
}

/** Relit l'état. Tant qu'une analyse tourne, on redemande toutes les 1,5 s ; à la fin, on
 *  réaffiche la page pour montrer les nouveaux résultats. */
export async function rafraichirEtat() {
  const avant = etat;
  etat = await api("etat");
  afficherEtat();
  if (etat.analyse_en_cours) {
    setTimeout(rafraichirEtat, 1500);
  }
  const analyseFinie = avant && avant.analyse_en_cours && !etat.analyse_en_cours;
  const nomsArrives = avant && avant.etape !== etat.etape && etat.pret;
  if (!avant || analyseFinie || nomsArrives || (avant.pret !== etat.pret)) {
    await afficherPage();
  }
}

/** Enregistre des réglages puis relance l'analyse (sans relire la source si ce n'est pas utile). */
export async function relancer(reglagesModifies = null, rechargerSource = false) {
  if (reglagesModifies) await api("reglages", "PUT", reglagesModifies);
  await api("analyse", "POST", { recharger_source: rechargerSource });
  await rafraichirEtat();
}

// ------------------------------------------------------------------ démarrage ---------
document.getElementById("choix-semaine").addEventListener("change", e => relancer({ semaine_ref: e.target.value }));
document.getElementById("choix-fenetre").addEventListener("change", e => relancer({ fenetre_semaines: Number(e.target.value) }));
document.getElementById("bouton-analyse").addEventListener("click", () => relancer(null, true));

// Un clic sur une clé de ticket, n'importe où dans la page, ouvre son détail.
document.addEventListener("click", evenement => {
  const lien = evenement.target.closest("[data-ticket]");
  if (lien) ouvrirTicket(lien.dataset.ticket);
});

// À chaque changement de page, on relit aussi l'état (source, LLM, compteurs) : il peut
// avoir changé, par exemple si le serveur a été redémarré avec un nouveau fichier .env.
window.addEventListener("hashchange", async () => {
  etat = await api("etat");
  afficherEtat();
  await afficherPage();
});
rafraichirEtat();
