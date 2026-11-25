// Page « Gain estimé » : les heures économisées par an si l'on traite la cause de chaque
// problème récurrent, selon trois scénarios.
import { api, esc, nb, graphique, optionsGraphique, ATTENTE } from "../outils.js";

export async function afficher(zone) {
  const d = await api("gain");
  if (!d.pret) { zone.innerHTML = ATTENTE; return; }
  const pct = t => nb(t * 100) + " %";

  zone.innerHTML = `
    <div class="pile">
      ${d.avertissements.map(a => `<div class="bandeau attention"><div>${esc(a)}</div></div>`).join("")}
      <div class="grille g3">
        ${[["pessimiste", "Scénario pessimiste"], ["median", "Scénario médian"], ["optimiste", "Scénario optimiste"]].map(([cle, titre]) => `
          <div class="carte indicateur"><p class="discret">${titre}</p>
            <p class="valeur">${nb(d.total[cle])} h<small> / an</small></p>
            <p class="discret petit">${pct(d.taux[cle])} des tickets évités une fois la cause traitée</p></div>`).join("")}
      </div>
      <div class="carte">
        <h3>Comment le gain est-il calculé ?</h3>
        <p class="discret">Gain annuel = heures consommées par semaine × 52 semaines × part des tickets évités.
          Les heures par semaine sont mesurées sur les ${d.nb_semaines} semaine(s) analysées. Les trois parts
          (${pct(d.taux.pessimiste)}, ${pct(d.taux.median)}, ${pct(d.taux.optimiste)}) sont des hypothèses, modifiables dans
          « Connecteurs et seuils ». Seuls les problèmes récurrents sont comptés.</p>
      </div>
      <div class="carte">
        <div class="titre-carte"><h2>Gain par problème</h2><span class="discret petit">trié par gain médian</span></div>
        ${d.problemes.length ? `
        <div class="hauteur-graphique" style="height:${60 + 34 * d.problemes.length}px"><canvas id="graphique-gain"></canvas></div>
        <div class="defilant"><table style="margin-top:14px">
          <thead><tr><th>Problème</th><th class="droite">Tickets</th><th class="droite">Heures consommées</th>
            <th class="droite">Heures / semaine</th><th class="droite">Pessimiste</th><th class="droite">Médian</th><th class="droite">Optimiste</th></tr></thead>
          <tbody>${d.problemes.map(p => `<tr class="cliquable" data-lien="#/problemes/${p.id}">
            <td><strong>${esc(p.nom)}</strong><span class="sous">${esc(p.application)}</span></td>
            <td class="droite chiffres">${nb(p.tickets)}</td><td class="droite chiffres">${nb(p.heures_total)} h</td>
            <td class="droite chiffres">${nb(p.heures_par_semaine, 1)} h</td><td class="droite chiffres">${nb(p.gain.pessimiste)} h</td>
            <td class="droite chiffres fort">${nb(p.gain.median)} h</td><td class="droite chiffres">${nb(p.gain.optimiste)} h</td></tr>`).join("")}</tbody>
        </table></div>` : '<p class="vide">Aucun problème récurrent : pas de gain à estimer.</p>'}
      </div>
    </div>`;

  zone.querySelectorAll("[data-lien]").forEach(l => l.addEventListener("click", () => { location.hash = l.dataset.lien; }));
  if (!d.problemes.length) return;
  // Barres horizontales : du scénario pessimiste (foncé) à l'optimiste (clair).
  const court = nom => nom.length > 46 ? nom.slice(0, 44) + "…" : nom;
  graphique(document.getElementById("graphique-gain"), {
    type: "bar",
    data: { labels: d.problemes.map(p => court(p.nom)), datasets: [
      { label: "pessimiste", data: d.problemes.map(p => p.gain.pessimiste), backgroundColor: "#0f766e" },
      { label: "médian", data: d.problemes.map(p => p.gain.median), backgroundColor: "#5bb5a6" },
      { label: "optimiste", data: d.problemes.map(p => p.gain.optimiste), backgroundColor: "#bfe3da" }] },
    options: { ...optionsGraphique, indexAxis: "y",
               scales: { x: { beginAtZero: true, title: { display: true, text: "heures par an" } }, y: { grid: { display: false } } } },
  });
}
