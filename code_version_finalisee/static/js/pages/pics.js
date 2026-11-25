// Page « Pics et alertes » : les semaines où un problème a explosé anormalement.
import { api, esc, nb, cles, graphique, optionsGraphique, ATTENTE } from "../outils.js";

export async function afficher(zone) {
  const d = await api("pics");
  if (!d.pret) { zone.innerHTML = ATTENTE; return; }
  const r = d.regles;

  const cartes = d.pics.map((p, i) => `
    <div class="carte">
      <div class="titre-carte">
        <h2><a href="#/problemes/${p.groupe}">${esc(p.nom)}</a></h2>
        <span class="etiquette ${p.est_semaine_ref ? "orange" : "gris"}">${p.est_semaine_ref ? "Semaine de référence" : "Pic passé"} · ${esc(p.etiquette)}</span>
      </div>
      <div class="grille g2">
        <div>
          <p><strong class="orange" style="font-size:22px">${p.observe} tickets</strong> pour ${nb(p.attendu, 1)} attendus
            (${nb(p.observe / p.attendu, 1)} fois le niveau habituel).</p>
          <p class="discret">Probabilité d'un tel volume par hasard : ${p.p_valeur < 0.001 ? "moins de 0,1 %" : nb(p.p_valeur * 100, 2) + " %"}
            (p = ${p.p_valeur.toExponential(1).replace(".", ",")}).</p>
          <p><strong>Application :</strong> ${esc(p.application)}</p>
          <p><strong>Solution habituelle :</strong> ${esc(p.solution) || "aucune notée"}</p>
          <p><strong>Tickets de la semaine :</strong> ${cles(p.cles)}</p>
        </div>
        <div class="hauteur-graphique" style="height:180px"><canvas id="graphique-pic-${i}"></canvas></div>
      </div>
    </div>`).join("");

  zone.innerHTML = `
    <div class="pile">
      <div class="carte">
        <h3>Comment un pic est-il détecté ?</h3>
        <p class="discret">Pour chaque problème et chaque semaine, on compare le nombre de tickets au niveau habituel
          (la médiane des semaines précédentes) avec un test de Poisson. Un pic est déclaré si la probabilité d'observer
          ce volume par hasard est inférieure à ${nb(r.alpha * 100, 2)} %, avec au moins ${r.pic_min} tickets et
          ${r.historique} semaines d'historique. Ces seuils se règlent dans « Connecteurs et seuils ».</p>
      </div>
      ${cartes || `<div class="carte"><p class="vide">Aucun pic anormal détecté sur la période
        (semaine de référence S${d.semaine_ref.numero}).</p></div>`}
    </div>`;

  d.pics.forEach((p, i) => graphique(document.getElementById("graphique-pic-" + i), {
    type: "bar",
    data: { labels: d.etiquettes, datasets: [{ label: "tickets", data: p.serie, borderRadius: 3,
            backgroundColor: d.numeros.map(n => n === p.semaine ? "#c2410c" : "#bfe3da") }] },
    options: { ...optionsGraphique, plugins: { legend: { display: false } } },
  }));
}
