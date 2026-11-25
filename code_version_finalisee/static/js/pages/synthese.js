// Page « Synthèse hebdomadaire » : générée par le moteur (sans LLM), exportable en Markdown.
import { api, esc, nb, cles, ATTENTE } from "../outils.js";

let semaineChoisie = null;         // numéro de la semaine affichée (null = semaine de référence)

export async function afficher(zone) {
  let s;
  try {
    s = await api("synthese" + (semaineChoisie ? "?semaine=" + semaineChoisie : ""));
  } catch (erreur) {
    if (semaineChoisie) { semaineChoisie = null; return afficher(zone); }   // semaine sortie de la période
    zone.innerHTML = ATTENTE;
    return;
  }
  const numero = s.semaine.numero, avant = s.semaine_precedente;
  const evolution = avant && avant.nb_tickets ? Math.round(100 * (s.nb_tickets - avant.nb_tickets) / avant.nb_tickets) : null;

  zone.innerHTML = `
    <div class="pile">
      <div class="carte" style="display:flex;gap:12px;align-items:flex-end;flex-wrap:wrap">
        <label class="fort" style="display:flex;flex-direction:column;gap:4px">Semaine
          <select id="choix-synthese">${[...s.semaines].reverse().map(x =>
            `<option value="${x.numero}" ${x.numero === numero ? "selected" : ""}>S${x.numero} · ${esc(x.libelle)}</option>`).join("")}</select></label>
        <a class="bouton principal" href="/api/synthese.md?semaine=${numero}" download>Exporter en Markdown</a>
        <button class="bouton" id="copier-synthese">Copier le texte</button>
        <span class="discret petit">Chiffres calculés par le moteur : disponibles même sans LLM.</span>
      </div>

      <div class="grille g4">
        <div class="carte indicateur"><p class="discret">Tickets créés</p><p class="valeur">${nb(s.nb_tickets)}</p>
          <p class="discret petit">${evolution === null ? "pas de semaine précédente" : `${evolution >= 0 ? "+" : ""}${evolution} % par rapport à S${numero - 1}`}</p></div>
        <div class="carte indicateur"><p class="discret">Heures consommées</p><p class="valeur">${nb(s.heures)} h</p>
          <p class="discret petit">${avant ? `${nb(avant.heures)} h la semaine précédente` : ""}</p></div>
        <div class="carte indicateur"><p class="discret">Pics anormaux</p><p class="valeur ${s.pics.length ? "orange" : ""}">${s.pics.length}</p>
          <p class="discret petit">${s.pics.map(p => esc(p.nom)).join(" · ") || "aucun"}</p></div>
        <div class="carte indicateur"><p class="discret">Tickets sans problème connu</p><p class="valeur">${s.nouveaux.nombre}</p>
          <p class="discret petit">${s.nouveaux.exemples.length ? cles(s.nouveaux.exemples.map(e => e.cle)) : "tous rattachés"}</p></div>
      </div>

      <div class="carte">
        <div class="titre-carte"><h2>Problèmes les plus présents en S${numero}</h2></div>
        ${s.problemes.length ? `<div class="defilant"><table>
          <thead><tr><th>Problème</th><th class="droite">Tickets</th><th class="droite">Niveau habituel</th><th class="droite">Heures</th><th>Exemples</th></tr></thead>
          <tbody>${s.problemes.map(p => `<tr><td><a href="#/problemes/${p.id}">${esc(p.nom)}</a>
              ${p.statut === "a_verifier" ? '<span class="etiquette jaune">À vérifier</span>' : ""}</td>
            <td class="droite chiffres">${p.tickets}</td><td class="droite chiffres">${p.habituel === null ? "–" : nb(p.habituel, 1)}</td>
            <td class="droite chiffres">${nb(p.heures, 1)} h</td><td>${cles(p.cles.slice(0, 3))}</td></tr>`).join("")}</tbody></table></div>`
          : '<p class="vide">Aucun ticket rattaché à un problème connu cette semaine.</p>'}
      </div>

      <div class="carte">
        <div class="titre-carte"><h2>Texte de la synthèse (Markdown)</h2></div>
        <pre class="markdown" id="texte-synthese">${esc(s.markdown)}</pre>
      </div>
    </div>`;

  document.getElementById("choix-synthese").addEventListener("change", evenement => {
    semaineChoisie = Number(evenement.target.value);
    afficher(zone);
  });
  document.getElementById("copier-synthese").addEventListener("click", async evenement => {
    await navigator.clipboard.writeText(s.markdown);
    evenement.target.textContent = "Copié";
  });
}
