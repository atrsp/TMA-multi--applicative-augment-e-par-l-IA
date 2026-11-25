// Page « Copilote » : le chat en grand, avec le rappel de ses règles de fonctionnement.
import { monterChat } from "../chat.js";

export async function afficher(zone, _parametre, etat) {
  zone.innerHTML = `
    <div class="grille deux-colonnes">
      <div class="carte"><div id="zone-chat-plein"></div></div>
      <div class="pile">
        <div class="carte">
          <h3>Comment travaille le copilote</h3>
          <ul style="margin:0;padding-left:18px">
            <li><strong>Le code calcule.</strong> Chaque chiffre vient d'un outil du moteur d'analyse ; les outils
              appelés sont affichés au-dessus de chaque réponse.</li>
            <li><strong>Le LLM rédige.</strong> Il explique, résume et propose, en citant les clés de tickets.
              Une clé citée qui n'existe pas est signalée.</li>
            <li><strong>Vous validez.</strong> Un plan proposé attend votre décision dans « Plans d'action ».</li>
            <li><strong>Lecture seule.</strong> Le copilote n'a aucun moyen de modifier Jira.</li>
          </ul>
        </div>
        <div class="carte">
          <h3>Outils disponibles</h3>
          <p class="outils-appeles" style="line-height:2"><code>top_recurrences</code><code>pics</code><code>gain_estime</code>
            <code>detail_probleme</code><code>tickets_similaires</code><code>detail_ticket</code>
            <code>synthese_hebdo</code><code>proposer_plan_action</code></p>
          <p class="discret petit">Seuls des extraits (titres, résumés) sont envoyés au LLM, jamais les tickets complets.
            ${etat?.llm?.actif ? `Modèle : ${etat.llm.modele}.` : ""}</p>
        </div>
      </div>
    </div>`;
  monterChat(document.getElementById("zone-chat-plein"), etat, true);
}
