// Page « Problèmes récurrents » : la liste (récurrents, ponctuels, à vérifier) et la fiche
// détaillée d'un problème (« #/problemes/3 »).
import { api, esc, nb, cle, cles, date, tendance, etiquettePlan, etiquetteStatut, graphique, optionsGraphique, ATTENTE } from "../outils.js";
import { cartePlan } from "../carte_plan.js";
import { rafraichirEtat } from "../app.js";

/** Un tableau de groupes. `avecGain` : afficher les colonnes gain et plan. */
function tableau(groupes, premiere, avecGain) {
  const lignes = groupes.map(g => `
    <tr class="cliquable" data-lien="#/problemes/${g.id}">
      <td><strong>${esc(g.nom)}</strong><span class="sous">${esc(g.application)} · ${esc(g.type)}
        ${g.origine_nom === "llm" ? " · nom rédigé par le LLM" : ""}${g.motif_verification === "texte_recopie" ? " · texte recopié"
            : g.motif_verification === "heterogene" ? ` · groupe hétérogène (cohésion ${nb(g.cohesion, 2)})` : ""}</span></td>
      <td class="droite chiffres">${nb(g.tickets)}</td>
      <td class="droite chiffres">${g.semaines_actives}</td>
      <td>${tendance(g.serie, g.pics.map(s => s - premiere))}</td>
      <td class="droite chiffres">${nb(g.heures_total)} h</td>
      ${avecGain ? `<td class="droite chiffres">${nb(g.gain.median)} h</td><td>${etiquettePlan(g.plan)}</td>` : ""}
    </tr>`).join("");
  return `<div class="defilant"><table><thead><tr><th>Problème</th><th class="droite">Tickets</th>
    <th class="droite">Semaines actives</th><th>Tendance</th><th class="droite">Heures</th>
    ${avecGain ? '<th class="droite">Gain médian / an</th><th>Plan</th>' : ""}</tr></thead><tbody>${lignes}</tbody></table></div>`;
}

async function afficherListe(zone) {
  const d = await api("problemes");
  if (!d.pret) { zone.innerHTML = ATTENTE; return; }
  const premiere = Number((d.etiquettes[0] || "S1").slice(1).split(" ")[0]);
  zone.innerHTML = `
    <div class="pile">
      <div class="carte">
        <div class="titre-carte"><h2>Problèmes récurrents (${d.recurrents.length})</h2>
          <span class="discret petit">groupes de tickets semblables, présents sur plusieurs semaines · triés par heures</span></div>
        ${d.recurrents.length ? tableau(d.recurrents, premiere, true) : '<p class="vide">Aucun problème récurrent sur la période.</p>'}
      </div>
      ${d.ponctuels.length ? `<div class="carte">
        <div class="titre-carte"><h2>Problèmes ponctuels (${d.ponctuels.length})</h2>
          <span class="discret petit">concentrés sur peu de semaines : pas (encore) des récurrences</span></div>
        ${tableau(d.ponctuels, premiere, false)}</div>` : ""}
      ${d.a_verifier.length ? `<div class="carte">
        <div class="titre-carte"><h2>Groupes à vérifier (${d.a_verifier.length})</h2>
          <span class="etiquette jaune">non comptés comme récurrences</span></div>
        <p class="discret">Deux cas : un <strong>même texte recopié</strong> à l'identique (doublons, gabarit de saisie ou vrai
          besoin répété ?), ou un <strong>groupe hétérogène</strong> dont les tickets se ressemblent trop peu pour former un
          seul problème. Ils ne sont comptés ni dans les récurrences ni dans le gain : à l'équipe de trancher.</p>
        ${tableau(d.a_verifier, premiere, false)}</div>` : ""}
    </div>`;
  zone.querySelectorAll("[data-lien]").forEach(l => l.addEventListener("click", () => { location.hash = l.dataset.lien; }));
}

async function afficherFiche(zone, identifiant) {
  const g = await api("problemes/" + identifiant);
  const picsSemaines = g.pics.map(p => p.semaine);
  const gain = g.gain
    ? `<p class="valeur">${nb(g.gain.median)} h<small> / an</small></p>
       <p class="discret petit">pessimiste ${nb(g.gain.pessimiste)} h · optimiste ${nb(g.gain.optimiste)} h</p>`
    : `<p class="valeur">–</p><p class="discret petit">non estimé : ${g.statut === "a_verifier" ? "groupe à vérifier" : "problème non récurrent"}</p>`;

  zone.innerHTML = `
    <p><a href="#/problemes">← Tous les problèmes</a></p>
    <div class="pile">
      <div class="carte">
        <p class="discret petit">Problème n° ${g.id} · ${esc(g.application)} · ${esc(g.type)} ${etiquetteStatut(g.statut)}</p>
        <h2 style="font-size:20px;margin:4px 0 10px">${esc(g.nom)}</h2>
        ${g.statut === "a_verifier" ? `<div class="bandeau attention"><div><strong>Groupe à vérifier.</strong>
          ${g.motif_verification === "texte_recopie"
            ? `${Math.round(g.part_texte_dominant * 100)} % de ses tickets portent exactement le même texte`
            : `Ses tickets se ressemblent trop peu (cohésion ${nb(g.cohesion, 2)}) : il mélange probablement plusieurs sujets`} :
          ce n'est pas présenté comme un problème récurrent.</div></div>` : ""}
        <h3>Description détaillée <span class="discret petit" style="font-weight:400">
          — ${g.origine_nom === "llm" ? "rédigée par le LLM à partir des seuls éléments ci-dessous, puis vérifiée" : "assemblée par le moteur à partir des tickets (sans LLM)"}</span></h3>
        <p>${esc(g.description)}</p>
        <div class="grille g2" style="margin-top:14px">
          <div><h3>Formulations représentatives</h3>
            <ul style="margin:0;padding-left:18px">${g.exemples.map(e => `<li>${esc(e)}</li>`).join("")}</ul></div>
          <div><h3>Mots caractéristiques</h3><p>${g.mots_cles.map(m => `<span class="mot">${esc(m)}</span>`).join("")}</p>
            <h3 style="margin-top:10px">Solution habituelle</h3>
            <p>${g.solution ? `${esc(g.solution)} <span class="discret">(notée dans ${g.solution_nb} ticket(s) sur ${g.tickets})</span>` : "Aucune résolution notée dans les tickets."}</p></div>
        </div>
      </div>

      <div class="grille g4">
        <div class="carte indicateur"><p class="discret">Tickets</p><p class="valeur">${nb(g.tickets)}</p>
          <p class="discret petit">${nb(g.par_semaine, 1)} par semaine · ${g.semaines_actives} semaine(s) active(s) sur ${g.nb_semaines}</p></div>
        <div class="carte indicateur"><p class="discret">Heures consommées</p><p class="valeur">${nb(g.heures_total)} h</p>
          <p class="discret petit">${nb(g.heures_moy, 1)} h par ticket en moyenne</p></div>
        <div class="carte indicateur"><p class="discret">Gain annuel estimé</p>${gain}</div>
        <div class="carte indicateur"><p class="discret">Pics détectés</p><p class="valeur ${g.pics.length ? "orange" : ""}">${g.pics.length}</p>
          <p class="discret petit">${g.pics.map(p => `S${p.semaine} : ${p.observe} pour ${nb(p.attendu, 1)} attendus`).join(" · ") || "aucune semaine anormale"}</p></div>
      </div>

      <div class="grille g2">
        <div class="carte"><div class="titre-carte"><h2>Tickets par semaine</h2></div>
          <div class="hauteur-graphique"><canvas id="graphique-serie"></canvas></div></div>
        <div class="carte"><div class="titre-carte"><h2>Plans d'action</h2></div>
          <div id="plans-du-probleme" class="pile"></div>
          ${g.statut === "a_verifier" ? "" : `
          <details style="margin-top:10px"><summary class="fort" style="cursor:pointer">Proposer un plan à la main</summary>
            <p class="petit fort" style="margin-top:10px">Titre</p><input id="plan-titre" style="width:100%" maxlength="200">
            <p class="petit fort" style="margin-top:8px">Actions (une par ligne)</p><textarea id="plan-actions" rows="4"></textarea>
            <div class="boutons"><button class="bouton principal" id="plan-creer">Enregistrer la proposition</button></div>
            <p class="petit orange" id="plan-erreur"></p></details>`}
        </div>
      </div>

      <div class="carte"><div class="titre-carte"><h2>Tickets du problème</h2>
          <span class="discret petit">${g.tickets_liste.length} affiché(s) sur ${g.tickets}, du plus récent au plus ancien</span></div>
        <div class="defilant" style="max-height:420px;overflow-y:auto"><table>
          <thead><tr><th>Clé</th><th>Titre</th><th>Créé le</th><th>Semaine</th><th class="droite">Heures</th><th class="droite">Ressemblance</th></tr></thead>
          <tbody>${g.tickets_liste.map(t => `<tr><td>${cle(t.cle)}</td><td>${esc(t.titre)}</td><td>${date(t.cree)}</td>
            <td>S${t.semaine}</td><td class="droite chiffres">${nb(t.heures, 1)}</td><td class="droite chiffres">${nb(t.score, 2)}</td></tr>`).join("")}</tbody>
        </table></div></div>
    </div>`;

  graphique(document.getElementById("graphique-serie"), {
    type: "bar",
    data: { labels: g.etiquettes, datasets: [{ label: "tickets", data: g.serie, borderRadius: 3,
            backgroundColor: g.numeros.map(n => picsSemaines.includes(n) ? "#c2410c" : "#7cc4b5") }] },
    options: { ...optionsGraphique, plugins: { legend: { display: false } } },
  });

  const zonePlans = document.getElementById("plans-du-probleme");
  const recharger = () => { rafraichirEtat(); afficherFiche(zone, identifiant); };
  if (g.plans.length) g.plans.forEach(p => zonePlans.appendChild(cartePlan({ ...p, probleme_id: g.id }, recharger)));
  else zonePlans.innerHTML = '<p class="discret">Aucun plan pour ce problème.</p>';

  document.getElementById("plan-creer")?.addEventListener("click", async () => {
    const actions = document.getElementById("plan-actions").value.split("\n").map(a => a.trim()).filter(Boolean);
    try {
      await api("plans", "POST", { probleme_id: g.id, titre: document.getElementById("plan-titre").value.trim(), actions });
      recharger();
    } catch (erreur) {
      document.getElementById("plan-erreur").textContent = "Renseignez un titre et au moins une action. " + erreur.message;
    }
  });
}

export async function afficher(zone, identifiant) {
  if (identifiant) return afficherFiche(zone, identifiant);
  return afficherListe(zone);
}
