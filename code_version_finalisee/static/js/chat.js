// =====================================================================================
// Le chat du copilote. Le même composant sert dans le tableau de bord (panneau de droite)
// et dans la page « Copilote » : la conversation est partagée entre les deux.
//
// Chaque réponse affiche : les outils appelés, le texte (clés de tickets cliquables), et
// les plans proposés avec leurs boutons Valider / Modifier / Rejeter.
// =====================================================================================
import { api, esc } from "./outils.js";
import { cartePlan } from "./carte_plan.js";
import { rafraichirEtat } from "./app.js";

/** La conversation en cours : une liste d'éléments {role, content, ...}. Gardée en mémoire
 *  du navigateur seulement (elle disparaît si l'on recharge la page). */
const conversation = [];

const SUGGESTIONS = [
  "Que doit-on traiter en priorité cette semaine ?",
  "Y a-t-il un pic anormal ? Explique-le.",
  "Fais la synthèse de la semaine.",
  "Propose un plan d'action pour le problème le plus coûteux.",
];

/** Transforme le texte du LLM en HTML sûr : gras, listes, et clés de tickets cliquables.
 *  Le texte est d'abord échappé : rien de ce qu'écrit le LLM n'est interprété comme du HTML. */
function mettreEnForme(texte, clesCitees) {
  let html = esc(texte).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>").replace(/`([^`]+)`/g, "<code>$1</code>");
  for (const c of clesCitees || []) {
    html = html.replaceAll(new RegExp(`\\b${c}\\b`, "g"), `<a class="cle" data-ticket="${c}">${c}</a>`);
  }
  // Lignes -> paragraphes et listes.
  const blocs = [];
  let liste = null;                                     // la liste en cours de construction
  for (const ligne of html.split("\n")) {
    const puce = ligne.match(/^\s*(?:[-*•]|(\d+)[.)])\s+(.*)$/);
    if (puce) {
      const type = puce[1] ? "ol" : "ul";
      if (!liste || liste.type !== type) { liste = { type, items: [] }; blocs.push(liste); }
      liste.items.push(puce[2]);
    } else {
      liste = null;
      if (ligne.trim()) blocs.push(ligne.replace(/^#+\s*(.*)$/, "<strong>$1</strong>"));
    }
  }
  return blocs.map(b => typeof b === "string" ? `<p>${b}</p>`
    : `<${b.type}>${b.items.map(i => `<li>${i}</li>`).join("")}</${b.type}>`).join("");
}

/** Écrit un appel d'outil comme dans du code : top_recurrences(n=3). */
function texteOutil(appel) {
  const args = Object.entries(appel.arguments || {})
    .filter(([nom]) => !["actions", "titre", "tickets_sources", "texte"].includes(nom))
    .map(([nom, valeur]) => `${nom}=${JSON.stringify(valeur)}`).join(", ");
  return `<code title="${appel.erreur ? esc(appel.erreur) : ""}">${esc(appel.outil)}(${esc(args)})${appel.erreur ? " ⚠" : ""}</code>`;
}

/** Construit l'élément HTML d'un message de la conversation. */
function bulle(message) {
  const element = document.createElement("div");
  if (message.role === "user") {
    element.className = "bulle question";
    element.textContent = message.content;
    return element;
  }
  element.className = "bulle " + (message.erreur ? "erreur" : "reponse");
  const outils = message.outils?.length
    ? `<div class="outils-appeles">outils appelés ${message.outils.map(texteOutil).join("")}</div>`
    : (message.erreur ? "" : '<div class="outils-appeles">aucun outil appelé — réponse sans chiffre vérifié</div>');
  const inconnues = message.cles_inconnues?.length
    ? `<p class="petit orange">Attention : clé(s) citée(s) introuvable(s) dans la base : ${esc(message.cles_inconnues.join(", "))}.</p>` : "";
  element.innerHTML = outils + mettreEnForme(message.content, message.tickets_cites) + inconnues;
  for (const plan of message.plans || []) {
    const carte = cartePlan(plan, nouveau => { Object.assign(plan, nouveau); redessiner(); rafraichirEtat(); });
    carte.style.marginTop = "10px";
    element.appendChild(carte);
  }
  return element;
}

let redessiner = () => {};        // remplacée par monterChat : redessine le fil affiché

/** Installe le chat dans `zone`. `plein` = vrai pour la page Copilote (plus de hauteur). */
export function monterChat(zone, etat, plein = false) {
  const actif = etat?.llm?.actif;
  zone.innerHTML = `
    <div class="chat ${plein ? "plein" : ""} ${actif ? "" : "desactive"}">
      <div class="fil"></div>
      <div class="suggestions">${SUGGESTIONS.map(s => `<button>${esc(s)}</button>`).join("")}</div>
      <form class="saisie">
        <input name="question" placeholder="Posez une question sur vos tickets…" autocomplete="off" maxlength="2000">
        <button class="bouton principal" type="submit">Envoyer</button>
      </form>
    </div>`;
  const fil = zone.querySelector(".fil");
  const champ = zone.querySelector("input");

  redessiner = () => {
    fil.innerHTML = "";
    if (!actif) {
      fil.innerHTML = `<div class="bulle erreur"><strong>Copilote désactivé.</strong> Aucun LLM n'est configuré
        (fichier <code>.env</code>). Le tableau de bord, les récurrences, les pics et le rattachement des
        nouveaux tickets fonctionnent normalement. Voir « Connecteurs et seuils ».</div>`;
      return;
    }
    if (!conversation.length) {
      fil.innerHTML = `<p class="discret">Le copilote propose, vous décidez. Il obtient tous ses chiffres en
        appelant les outils du moteur d'analyse et cite les tickets sur lesquels il s'appuie.</p>`;
    }
    conversation.forEach(m => fil.appendChild(bulle(m)));
    fil.scrollTop = fil.scrollHeight;
  };
  redessiner();

  async function envoyer(question) {
    if (!question.trim() || !actif) return;
    conversation.push({ role: "user", content: question.trim() });
    const attente = { role: "assistant", content: "Le copilote consulte les analyses…", erreur: false, outils: [{ outil: "…", arguments: {} }] };
    conversation.push(attente);
    redessiner();
    try {
      const historique = conversation.filter(m => m !== attente && !m.erreur).map(m => ({ role: m.role, content: m.content }));
      const r = await api("copilote", "POST", { historique });
      let plans = [];
      if (r.plans_crees.length) {
        const tous = (await api("plans")).plans;
        plans = tous.filter(p => r.plans_crees.includes(p.id));
      }
      Object.assign(attente, { content: r.reponse, outils: r.outils, tickets_cites: r.tickets_cites,
                               cles_inconnues: r.cles_inconnues, plans });
      if (plans.length) rafraichirEtat();
    } catch (erreur) {
      Object.assign(attente, { content: erreur.message, erreur: true, outils: [] });
    }
    redessiner();
  }

  zone.querySelector("form").addEventListener("submit", evenement => {
    evenement.preventDefault();
    envoyer(champ.value);
    champ.value = "";
  });
  zone.querySelectorAll(".suggestions button").forEach(b => b.addEventListener("click", () => envoyer(b.textContent)));
}
