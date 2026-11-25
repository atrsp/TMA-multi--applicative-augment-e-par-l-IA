// =====================================================================================
// Petites fonctions utilisées par toutes les pages.
// =====================================================================================

/** Appelle l'API et renvoie la réponse décodée. En cas d'erreur, lève une Error lisible. */
export async function api(chemin, methode = "GET", corps = null) {
  const options = { method: methode, headers: {} };
  if (corps !== null) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(corps);
  }
  const reponse = await fetch("/api/" + chemin, options);
  const donnees = await reponse.json().catch(() => ({}));
  if (!reponse.ok) {
    const detail = typeof donnees.detail === "string" ? donnees.detail : "Demande refusée (valeur invalide).";
    throw new Error(detail);
  }
  return donnees;
}

/** Rend un texte inoffensif avant de l'insérer dans la page (protection contre l'injection HTML).
 *  À utiliser pour TOUT texte venant des tickets ou du LLM. */
export function esc(texte) {
  return String(texte ?? "").replace(/[&<>"']/g, c =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

/** Écrit un nombre à la française : 1106.7 -> « 1 106,7 ». */
export function nb(valeur, decimales = 0) {
  if (valeur === null || valeur === undefined) return "–";
  return Number(valeur).toLocaleString("fr-FR", { maximumFractionDigits: decimales });
}

/** Écrit une date ISO en « 27/07/2026 ». */
export function date(iso) {
  if (!iso) return "–";
  const [a, m, j] = iso.slice(0, 10).split("-");
  return `${j}/${m}/${a}`;
}

/** Une clé de ticket cliquable (ouvre la fenêtre de détail). */
export function cle(c) {
  return `<a class="cle" data-ticket="${esc(c)}">${esc(c)}</a>`;
}

/** Une liste de clés cliquables, séparées par des virgules. */
export function cles(liste) {
  return (liste || []).map(cle).join(", ");
}

/** L'étiquette colorée du statut d'un problème. */
export function etiquetteStatut(statut) {
  const formes = {
    recurrent: ["vert", "Récurrent"], ponctuel: ["bleu", "Ponctuel"], a_verifier: ["jaune", "À vérifier"],
  };
  const [couleur, texte] = formes[statut] || ["gris", statut];
  return `<span class="etiquette ${couleur}">${texte}</span>`;
}

/** L'étiquette du plan d'action lié à un problème. */
export function etiquettePlan(statut) {
  const formes = { propose: ["jaune", "À valider"], valide: ["vert", "Validé"], rejete: ["gris", "Rejeté"] };
  const [couleur, texte] = formes[statut] || ["gris", "Aucun"];
  return `<span class="etiquette ${couleur}">${texte}</span>`;
}

/** Petite courbe de tendance dessinée en SVG. `indicesPics` : positions à marquer d'un point. */
export function tendance(serie, indicesPics = []) {
  if (!serie || serie.length < 2) return "";
  const largeur = 110, hauteur = 26, max = Math.max(...serie, 1);
  const x = i => (i / (serie.length - 1)) * (largeur - 6) + 3;
  const y = v => hauteur - 3 - (v / max) * (hauteur - 6);
  const points = serie.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  const couleur = indicesPics.length ? "#c2410c" : "#0f766e";
  const marques = indicesPics.map(i =>
    `<circle cx="${x(i).toFixed(1)}" cy="${y(serie[i]).toFixed(1)}" r="2.6" fill="#c2410c"/>`).join("");
  return `<svg width="${largeur}" height="${hauteur}" role="img" aria-label="tendance hebdomadaire">
            <polyline points="${points}" fill="none" stroke="${couleur}" stroke-width="1.6"/>${marques}</svg>`;
}

/** La jauge de ressemblance d'un ticket, avec le trait du seuil. */
export function jauge(score, seuil) {
  const pct = Math.max(0, Math.min(1, score)) * 100;
  return `<div class="jauge"><div class="barre"><i class="${score < seuil ? "faible" : ""}" style="width:${pct}%"></i>
            <b style="left:${seuil * 100}%" title="seuil ${nb(seuil, 2)}"></b></div>
            <strong class="chiffres">${nb(score, 2)}</strong></div>`;
}

/** Dessine un graphique Chart.js dans un <canvas>. Renvoie null si Chart.js n'a pas pu être chargé. */
export function graphique(canvas, configuration) {
  if (!window.Chart) {
    canvas.parentElement.innerHTML = '<p class="vide">Graphique indisponible (Chart.js non chargé : vérifiez la connexion Internet).</p>';
    return null;
  }
  return new window.Chart(canvas, configuration);
}

/** Options communes aux graphiques hebdomadaires. */
export const optionsGraphique = {
  responsive: true, maintainAspectRatio: false,
  plugins: { legend: { position: "top", align: "end", labels: { boxWidth: 12, font: { size: 11 } } } },
  scales: { x: { grid: { display: false }, ticks: { font: { size: 10 } } },
            y: { beginAtZero: true, ticks: { font: { size: 10 } } } },
};

/** Ouvre la fenêtre de détail d'un ticket. */
export async function ouvrirTicket(c) {
  const fenetre = document.getElementById("fenetre-ticket");
  try {
    const t = await api("tickets/" + encodeURIComponent(c));
    const probleme = t.probleme
      ? `<a href="#/problemes/${t.probleme.id}" data-fermer>${esc(t.probleme.nom)}</a> ${etiquetteStatut(t.probleme.statut)}`
      : "Aucun problème connu";
    fenetre.innerHTML = `
      <p class="discret petit">${esc(t.cle)} · ${esc(t.application)} · ${esc(t.type)} · priorité ${esc(t.priorite)}</p>
      <h2>${esc(t.titre)}</h2>
      <dl>
        <dt>Créé le</dt><dd>${date(t.cree)}${t.semaine ? ` (semaine S${t.semaine})` : ""}</dd>
        <dt>Temps passé</dt><dd>${nb(t.heures, 1)} h</dd>
        <dt>Statut</dt><dd>${esc(t.statut)}</dd>
        <dt>Problème</dt><dd>${probleme}${t.score != null ? ` <span class="discret">(ressemblance ${nb(t.score, 2)})</span>` : ""}</dd>
        <dt>Description</dt><dd>${esc(t.description) || "–"}</dd>
        <dt>Résolution</dt><dd>${esc(t.solution) || "–"}</dd>
      </dl>
      <div class="boutons"><button class="bouton" data-fermer>Fermer</button></div>`;
  } catch (erreur) {
    fenetre.innerHTML = `<p>${esc(erreur.message)}</p><button class="bouton" data-fermer>Fermer</button>`;
  }
  fenetre.querySelectorAll("[data-fermer]").forEach(e => e.addEventListener("click", () => fenetre.close()));
  fenetre.showModal();
}

/** Message affiché quand l'analyse n'est pas encore disponible. */
export const ATTENTE = '<p class="vide">Analyse en cours… la page se remplira automatiquement.</p>';
