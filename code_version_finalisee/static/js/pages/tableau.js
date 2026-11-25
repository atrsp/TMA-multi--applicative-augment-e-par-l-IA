// Page « Tableau de bord » : indicateurs, alerte de pic, problèmes les plus coûteux,
// volume hebdomadaire, derniers tickets et panneau du copilote.
import { api, esc, nb, cle, cles, tendance, jauge, etiquettePlan, etiquetteStatut, graphique, optionsGraphique, ATTENTE } from "../outils.js";
import { monterChat } from "../chat.js";

/** Les 4 cartes d'indicateurs du haut de page. */
function indicateurs(d) {
  const i = d.indicateurs;
  return `
    <div class="grille g4">
      <div class="carte indicateur"><p class="discret">Tickets récurrents</p>
        <p class="valeur">${nb(i.part_tickets_recurrents)} %</p>
        <p class="discret petit">des tickets relèvent de ${i.nb_problemes} problème(s) connu(s)${i.nb_a_verifier ? ` · ${i.nb_a_verifier} groupe(s) à vérifier` : ""}</p></div>
      <div class="carte indicateur"><p class="discret">Temps consommé par les récurrences</p>
        <p class="valeur">${nb(i.heures_recurrences)} h</p>
        <p class="discret petit">soit ${nb(i.part_heures)} % des ${nb(d.periode.heures_total)} h de la période</p></div>
      <div class="carte indicateur"><p class="discret">Gain annuel estimé</p>
        <p class="valeur">${nb(i.gain.median)} h</p>
        <p class="discret petit">fourchette ${nb(i.gain.pessimiste)} – ${nb(i.gain.optimiste)} h selon scénario</p></div>
      <div class="carte indicateur"><p class="discret">Plans d'action</p>
        <p class="valeur">${i.plans.propose} <small>à valider</small></p>
        <p class="petit"><span class="vert fort">${i.plans.valide} validé(s)</span> <span class="discret">· ${i.plans.rejete} rejeté(s)</span></p></div>
    </div>`;
}

/** Le bandeau d'alerte : pic de la semaine de référence, ou rappel des pics passés. */
function bandeauPic(d) {
  const a = d.alerte, ref = d.periode.semaine_ref;
  if (a) {
    return `<div class="bandeau pic"><span class="rond">!</span>
      <div><strong>Pic anormal détecté · ${esc(a.nom)}</strong> — ${a.observe} tickets en semaine S${a.semaine}
        pour ${nb(a.attendu, 1)} attendus (p ${a.p_valeur < 0.001 ? "< 0,001" : "= " + nb(a.p_valeur, 3)}).
        ${a.autres ? `${a.autres} autre(s) pic(s) cette semaine.` : ""}</div>
      <a class="bouton" href="#/pics">Voir l'analyse</a></div>`;
  }
  if (d.hebdo.nb_pics) {
    return `<div class="bandeau info"><div>Aucun pic en semaine S${ref.numero}. ${d.hebdo.nb_pics} pic(s) détecté(s) plus tôt
      dans la période (${d.hebdo.pics.map(s => "S" + s).join(", ")}).</div><a class="bouton" href="#/pics">Voir</a></div>`;
  }
  return "";
}

/** Le tableau des problèmes récurrents les plus coûteux. */
function tableauProblemes(d) {
  if (!d.problemes.length) return '<p class="vide">Aucun problème récurrent sur la période.</p>';
  const premiere = d.hebdo.numeros[0];
  const lignes = d.problemes.map(p => `
    <tr class="cliquable" data-lien="#/problemes/${p.id}">
      <td><strong>${esc(p.nom)}</strong><span class="sous">${esc(p.application)} · ${esc(p.type)}</span></td>
      <td class="droite chiffres">${nb(p.tickets)}</td>
      <td>${tendance(p.serie, p.pics.map(s => s - premiere))}</td>
      <td class="droite chiffres">${nb(p.heures_total)} h</td>
      <td class="droite chiffres">${nb(p.gain.median)} h</td>
      <td>${etiquettePlan(p.plan)}</td>
    </tr>`).join("");
  return `<div class="defilant"><table>
    <thead><tr><th>Problème</th><th class="droite">Tickets</th><th>Tendance</th><th class="droite">Heures</th>
      <th class="droite">Gain / an</th><th>Plan</th></tr></thead><tbody>${lignes}</tbody></table></div>`;
}

/** Un ticket récent avec son verdict « problème connu » ou « nouveau problème ». */
export function ticketEntrant(t) {
  const p = t.probleme;
  const verdict = !t.connu ? '<span class="etiquette gris">Nouveau problème</span>'
    : p.statut === "a_verifier" ? '<span class="etiquette jaune">Groupe à vérifier</span>'
    : '<span class="etiquette orange">Problème connu</span>';
  const suite = t.connu
    ? `<p class="petit" style="margin:8px 0 0"><a href="#/problemes/${p.id}">${esc(p.nom)}</a>
         ${p.solution ? `<br><strong>Solution habituelle (${p.solution_nb}/${p.tickets}) :</strong> ${esc(p.solution)}` : ""}</p>`
    : `<p class="petit discret" style="margin:8px 0 0">Sous le seuil de ${nb(t.seuil, 2)} : à traiter normalement.</p>`;
  return `<div class="ticket-entrant">
    <p class="petit discret">${cle(t.cle)} · ${esc(t.application)} · priorité ${esc(t.priorite)}</p>
    <p class="fort">${esc(t.titre)}</p>
    <div style="display:flex;gap:10px;align-items:center">${verdict}<div style="flex:1">${jauge(t.score, t.seuil)}</div></div>
    ${suite}</div>`;
}

/** Le graphique du volume hebdomadaire : barres = tous les tickets, courbe = groupe suivi. */
function dessinerVolume(canvas, h) {
  const couleurs = h.numeros.map(n => h.pics.includes(n) ? "#f4b8a0" : "#bfe3da");
  const series = [{ type: "bar", label: "tous tickets", data: h.total, backgroundColor: couleurs, borderRadius: 3, order: 2 }];
  if (h.suivi) {
    series.push({ type: "line", label: h.suivi.nom, data: h.suivi.serie, borderColor: "#c2410c",
                  backgroundColor: "#c2410c", borderWidth: 2, pointRadius: 2.5, tension: .25, order: 1 });
  }
  graphique(canvas, { data: { labels: h.etiquettes, datasets: series }, options: optionsGraphique });
}

export async function afficher(zone, _parametre, etat) {
  const d = await api("tableau-de-bord");
  if (!d.pret) { zone.innerHTML = ATTENTE; return; }
  const h = d.hebdo;
  const ecart = h.moyenne ? Math.round(100 * (h.valeur_ref - h.moyenne) / h.moyenne) : 0;

  zone.innerHTML = `
    <p class="discret" style="margin-top:-8px">Périmètre : ${d.periode.nb_applications} application(s) ·
      ${nb(d.periode.nb_tickets)} tickets analysés · ${d.periode.nb_semaines} semaine(s) depuis le
      ${d.periode.debut.split("-").reverse().join("/")}</p>
    ${indicateurs(d)}
    <div style="height:16px"></div>
    ${bandeauPic(d)}
    <div class="grille deux-colonnes">
      <div class="pile">
        <div class="carte">
          <div class="titre-carte"><h2>Problèmes récurrents les plus coûteux</h2>
            <span class="discret petit">regroupement automatique · trié par heures consommées</span></div>
          ${tableauProblemes(d)}
        </div>
        <div class="grille g2">
          <div class="carte">
            <div class="titre-carte"><h2>Volume hebdomadaire</h2></div>
            <div class="hauteur-graphique"><canvas id="graphique-volume"></canvas></div>
            <div class="grille g3" style="margin-top:12px;gap:8px">
              <div><p class="discret petit">Moyenne</p><p class="fort">${nb(h.moyenne)} / sem.</p></div>
              <div><p class="discret petit">Semaine S${d.periode.semaine_ref.numero}</p>
                <p class="fort ${Math.abs(ecart) >= 15 ? "orange" : ""}">${nb(h.valeur_ref)} (${ecart >= 0 ? "+" : ""}${ecart} %)</p></div>
              <div><p class="discret petit">Pics détectés</p><p class="fort">${h.nb_pics} sur ${d.periode.nb_semaines} sem.</p></div>
            </div>
          </div>
          <div class="carte">
            <div class="titre-carte"><h2>Derniers tickets de la semaine</h2><a class="petit" href="#/nouveaux">tout voir</a></div>
            ${d.nouveaux.length ? d.nouveaux.slice(0, 3).map(ticketEntrant).join("") : '<p class="vide">Aucun ticket cette semaine.</p>'}
          </div>
        </div>
      </div>
      <div class="carte">
        <div class="titre-carte"><h2>Copilote RUN</h2><span class="discret petit">propose · vous décidez</span></div>
        <div id="zone-chat"></div>
      </div>
    </div>`;

  zone.querySelectorAll("[data-lien]").forEach(l => l.addEventListener("click", () => { location.hash = l.dataset.lien; }));
  dessinerVolume(document.getElementById("graphique-volume"), h);
  monterChat(document.getElementById("zone-chat"), etat);
}
