/* Pannello Zyxel: stato della linea, conversazione e bande.
   Legge e comanda le entita' gia' esistenti, quindi non serve un'API a parte. */

const stile = `
  :host { display:block; padding:16px; }
  h1 { font-size:22px; font-weight:500; margin:0 0 16px; }
  h2 { font-size:16px; font-weight:500; margin:0 0 12px; }
  .riquadri { display:grid; gap:12px; margin-bottom:16px;
              grid-template-columns:repeat(auto-fit,minmax(130px,1fr)); }
  .riquadro { background:var(--ha-card-background,var(--card-background-color,#fff));
              border-radius:12px; padding:12px 14px;
              box-shadow:var(--ha-card-box-shadow,0 2px 4px rgba(0,0,0,.08)); }
  .etichetta { font-size:13px; color:var(--secondary-text-color); }
  .valore { font-size:24px; font-weight:500; color:var(--primary-text-color); }
  .valore .unita { font-size:13px; color:var(--secondary-text-color); font-weight:400; }
  .valore.testo { font-size:18px; padding-top:4px; }
  /* align-items:start, altrimenti la scheda delle bande si allunga per pareggiare
     quella dei messaggi e resta mezza vuota. */
  .colonne { display:grid; gap:16px; align-items:start;
             grid-template-columns:repeat(auto-fit,minmax(340px,1fr)); }
  .scheda { background:var(--ha-card-background,var(--card-background-color,#fff));
            border-radius:12px; padding:16px;
            box-shadow:var(--ha-card-box-shadow,0 2px 4px rgba(0,0,0,.08)); }
  .conversazione { margin-bottom:16px; }
  .conversazione + .conversazione { border-top:1px solid var(--divider-color,#e0e0e0);
                                    padding-top:14px; }
  .capo { display:flex; align-items:center; justify-content:space-between; gap:10px;
          margin-bottom:8px; }
  .chi { font-size:14px; font-weight:500; color:var(--primary-text-color); }
  .nuovo { border-top:1px solid var(--divider-color,#e0e0e0); padding-top:14px;
           margin-top:16px; }
  .esito:empty { display:none; }
  .bolla { border-radius:14px; padding:10px 12px; margin-bottom:8px; max-width:86%; }
  .bolla.sinistra { background:var(--secondary-background-color,#f1f1f1); }
  .bolla.destra { background:var(--primary-color,#03a9f4); margin-left:auto; }
  .bolla.destra .mittente, .bolla.destra .corpo { color:var(--text-primary-color,#fff); }
  .mittente { font-size:12px; color:var(--secondary-text-color); margin-bottom:3px;
              display:flex; justify-content:space-between; gap:10px; align-items:center; }
  .corpo { font-size:14px; color:var(--primary-text-color); white-space:pre-wrap;
           word-break:break-word; }
  .cestino { background:none; border:none; cursor:pointer; color:inherit; opacity:.45;
             padding:0; line-height:0; --mdc-icon-size:17px; }
  .cestino:hover { opacity:1; }
  .barra { display:flex; align-items:flex-end; gap:8px; margin-top:14px; }
  .barra textarea { flex:1; min-height:42px; border-radius:22px; padding:11px 16px;
                    background:var(--secondary-background-color,#f1f1f1);
                    border:1px solid transparent; }
  .barra textarea:focus { outline:none; border-color:var(--primary-color,#03a9f4); }
  .tondo { flex:none; width:42px; height:42px; border-radius:50%; border:none;
           cursor:pointer; background:var(--primary-color,#03a9f4);
           color:var(--text-primary-color,#fff); display:flex; align-items:center;
           justify-content:center; --mdc-icon-size:20px; }
  .tondo:disabled { opacity:.5; cursor:default; }
  .pastiglie { display:flex; flex-wrap:wrap; gap:6px; }
  .pastiglia { font-size:13px; padding:6px 14px; border-radius:999px; cursor:pointer;
               border:1px solid var(--divider-color,#ddd); background:none;
               color:var(--secondary-text-color); }
  .pastiglia.accesa { border-color:transparent; background:var(--primary-color,#03a9f4);
                      color:var(--text-primary-color,#fff); }
  .pastiglia.accesa.nr { background:var(--success-color,#43a047); }
  .riga { display:flex; gap:10px; align-items:center; margin-bottom:12px; flex-wrap:wrap; }
  input[type=text], select, textarea {
      font:inherit; padding:9px 10px; border-radius:10px;
      border:1px solid var(--divider-color,#ccc);
      background:var(--card-background-color,#fff); color:var(--primary-text-color); }
  textarea { width:100%; box-sizing:border-box; min-height:58px; resize:vertical; }
  button.azione { font:inherit; padding:9px 16px; border-radius:10px; border:none;
                  cursor:pointer; background:var(--primary-color,#03a9f4);
                  color:var(--text-primary-color,#fff); }
  button.azione:disabled { opacity:.5; cursor:default; }
  .nota { font-size:12px; color:var(--secondary-text-color); margin-top:10px; }
  .vuoto { font-size:14px; color:var(--secondary-text-color); }
`;

class PannelloZyxel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._disegnato = false;
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._disegnato) {
      this._costruisci();
      this._disegnato = true;
    }
    this._aggiorna();
  }

  /* --- ricerca delle entita' -------------------------------------------- */

  _trova(prefisso, pezzo) {
    const stati = this._hass ? this._hass.states : {};
    return Object.keys(stati).filter(
      (id) => id.startsWith(prefisso) && id.includes("zyxel") && id.includes(pezzo)
    );
  }

  _uno(prefisso, pezzo) {
    const trovati = this._trova(prefisso, pezzo);
    return trovati.length ? this._hass.states[trovati[0]] : null;
  }

  _stato(prefisso, pezzo, ripiego) {
    const ent = this._uno(prefisso, pezzo);
    return ent && ent.state !== "unknown" && ent.state !== "unavailable"
      ? ent.state
      : ripiego;
  }

  /* --- struttura --------------------------------------------------------- */

  _costruisci() {
    const radice = document.createElement("div");
    radice.innerHTML = `
      <style>${stile}</style>
      <h1>Zyxel</h1>
      <div class="riquadri">
        <div class="riquadro"><div class="etichetta">Segnale</div>
          <div class="valore" id="rsrp">—</div></div>
        <div class="riquadro"><div class="etichetta">Qualita'</div>
          <div class="valore" id="sinr">—</div></div>
        <div class="riquadro"><div class="etichetta">Banda</div>
          <div class="valore testo" id="banda">—</div></div>
        <div class="riquadro"><div class="etichetta">Rete</div>
          <div class="valore testo" id="rete">—</div></div>
      </div>
      <div class="colonne">
        <div class="scheda">
          <h2>Messaggi</h2>
          <div id="elenco"><div class="vuoto">Nessun messaggio.</div></div>
          <div class="nuovo">
            <div class="etichetta" style="margin-bottom:8px">Nuovo messaggio</div>
            <div class="riga">
              <input type="text" id="numero" placeholder="+39..." style="flex:1">
            </div>
            <div class="barra" style="margin-top:8px">
              <textarea id="testo" placeholder="Scrivi un messaggio" rows="1"></textarea>
              <button class="tondo" id="invia" aria-label="Invia">
                <ha-icon icon="mdi:send"></ha-icon>
              </button>
            </div>
            <div class="nota" id="esito"></div>
          </div>
        </div>
        <div class="scheda">
          <h2>Bande</h2>
          <div class="riga">
            <span class="etichetta">Tecnologia</span>
            <select id="tecnologia"></select>
          </div>
          <div class="riga">
            <button class="pastiglia" id="auto">Selezione automatica</button>
          </div>
          <div class="pastiglie" id="bande"></div>
          <div class="nota">Le blu sono 4G, le verdi 5G. L'ultima banda accesa non si
            puo' spegnere: resteresti senza linea.</div>
        </div>
      </div>`;
    this.shadowRoot.appendChild(radice);

    this.shadowRoot.getElementById("invia").addEventListener("click", () => this._invia());
    this.shadowRoot.getElementById("tecnologia").addEventListener("change", (e) => {
      const ent = this._uno("select.", "tecnologia");
      if (ent)
        this._hass.callService("select", "select_option", {
          entity_id: ent.entity_id,
          option: e.target.value,
        });
    });
    this.shadowRoot.getElementById("auto").addEventListener("click", () => {
      const ent = this._uno("switch.", "selezione_banda_automatica");
      if (!ent) return;
      this._hass.callService("switch", ent.state === "on" ? "turn_off" : "turn_on", {
        entity_id: ent.entity_id,
      });
    });
  }

  /* --- aggiornamento ------------------------------------------------------ */

  _aggiorna() {
    this._intestazione();
    this._messaggi();
    this._tecnologia();
    this._bande();
  }

  _intestazione() {
    const R = this.shadowRoot;
    const rsrp = this._stato("sensor.", "cellular_rsrp", null);
    const sinr = this._stato("sensor.", "cellular_sinr", null);
    R.getElementById("rsrp").innerHTML = rsrp
      ? `${rsrp}<span class="unita"> dBm</span>`
      : "—";
    R.getElementById("sinr").innerHTML = sinr ? `${sinr}<span class="unita"> dB</span>` : "—";
    R.getElementById("banda").textContent = (
      this._stato("sensor.", "cellular_current_band", "—") || "—"
    )
      .replace("LTE_BC", "B")
      .replace("NR5G_N", "n");
    R.getElementById("rete").textContent = this._stato(
      "sensor.", "cellular_current_access_technology", "—"
    );
  }

  _messaggi() {
    const ent = this._uno("sensor.", "sms_ricevuti");
    const box = this.shadowRoot.getElementById("elenco");
    const elenco = ent && ent.attributes.messaggi ? ent.attributes.messaggi : [];

    // hass cambia di continuo: si ridisegna solo quando l'elenco cambia davvero,
    // altrimenti la pagina sfarfalla e si perde il clic in corso.
    const firma = JSON.stringify(elenco);
    if (firma === this._firmaMessaggi) return;
    this._firmaMessaggi = firma;

    if (!elenco.length) {
      box.innerHTML = '<div class="vuoto">Nessun messaggio.</div>';
      return;
    }

    const fuga = (t) => (t || "").replace(/</g, "&lt;");

    // Una conversazione per interlocutore, dal piu' recente.
    const gruppi = new Map();
    elenco.forEach((m, i) => {
      const chi = (m.da || "sconosciuto").trim();
      if (!gruppi.has(chi)) gruppi.set(chi, []);
      gruppi.get(chi).push({ ...m, _i: i });
    });

    const ordinati = [...elenco];
    box.innerHTML = [...gruppi.entries()]
      .map(([chi, voci]) => {
        // Si risponde solo a un numero: i mittenti a lettere non lo accettano.
        const numero = /^\+?\d[\d ]*$/.test(chi);
        const bolle = voci
          .slice()
          .reverse()
          .map(
            // Ricevuti a sinistra, inviati a destra: il verso arriva dal campo
            // State della casella, non dal mittente.
            (m) => `<div class="bolla ${m.inviato ? "destra" : "sinistra"}">
              <div class="mittente">
                <span>${fuga(m.quando)}</span>
                <button class="cestino" data-riga="${m._i}" aria-label="Cancella"><ha-icon icon="mdi:trash-can-outline"></ha-icon></button>
              </div>
              <div class="corpo">${fuga(m.testo)}</div>
            </div>`
          )
          .join("");
        // La risposta sta dentro la sua conversazione: una casella sola in fondo
        // per piu' interlocutori si presta agli errori.
        const barra = numero
          ? `<div class="barra">
              <textarea class="risposta" data-numero="${fuga(chi)}" rows="1"
                        placeholder="Rispondi a ${fuga(chi)}"></textarea>
              <button class="tondo manda" data-numero="${fuga(chi)}" aria-label="Invia">
                <ha-icon icon="mdi:send"></ha-icon>
              </button>
            </div>
            <div class="nota esito" data-numero="${fuga(chi)}"></div>`
          : "";
        return `<div class="conversazione">
            <div class="capo"><span class="chi">${fuga(chi)}</span></div>
            ${bolle}
            ${barra}
          </div>`;
      })
      .join("");

    box.querySelectorAll("button.cestino").forEach((tasto) =>
      tasto.addEventListener("click", () => {
        const m = ordinati[Number(tasto.dataset.riga)];
        if (!m || !m.indici || !m.indici.length) return;
        if (!confirm("Cancellare questo messaggio?")) return;
        tasto.disabled = true;
        this._hass.callService("ha_zyxel", "elimina_sms", { indici: m.indici });
      })
    );

    // Le bozze non devono sparire quando arriva un messaggio e si ridisegna.
    box.querySelectorAll("textarea.risposta").forEach((campo) => {
      const bozza = (this._bozze || {})[campo.dataset.numero];
      if (bozza) campo.value = bozza;
      campo.addEventListener("input", () => {
        this._bozze = this._bozze || {};
        this._bozze[campo.dataset.numero] = campo.value;
      });
    });

    box.querySelectorAll("button.manda").forEach((tasto) =>
      tasto.addEventListener("click", () => this._manda(tasto.dataset.numero))
    );
  }

  _tecnologia() {
    const ent = this._uno("select.", "tecnologia");
    const menu = this.shadowRoot.getElementById("tecnologia");
    if (!ent) { menu.innerHTML = ""; return; }
    const atteso = (ent.attributes.options || [])
      .map((o) => `<option value="${o}">${o}</option>`)
      .join("");
    if (menu.innerHTML !== atteso) menu.innerHTML = atteso;
    if (menu.value !== ent.state) menu.value = ent.state;
  }

  _bande() {
    const automatica = this._uno("switch.", "selezione_banda_automatica");
    const tasto = this.shadowRoot.getElementById("auto");
    tasto.classList.toggle("accesa", !!automatica && automatica.state === "on");

    // "selezione_banda_automatica" contiene "_banda_": va escluso, ha gia' il suo
    // tasto. E l'ordine giusto e' B1,B3,B7,B20... non quello alfabetico.
    const ids = this._trova("switch.", "_banda_")
      .filter((id) => !id.includes("automatica"))
      .sort((a, b) => {
        const chiave = (id) => {
          const m = /_banda_([a-z]+)(\d+)$/.exec(id);
          return m ? [m[1] === "b" ? 0 : 1, parseInt(m[2], 10)] : [9, 0];
        };
        const [ta, na] = chiave(a);
        const [tb, nb] = chiave(b);
        return ta - tb || na - nb;
      });

    const box = this.shadowRoot.getElementById("bande");
    if (box.childElementCount !== ids.length) {
      box.innerHTML = ids
        .map((id) => {
          const nome = (this._hass.states[id].attributes.friendly_name || id).replace(
            /^.*\bBanda\b\s*/i, ""
          );
          return `<button class="pastiglia" data-id="${id}">${nome}</button>`;
        })
        .join("");
      box.querySelectorAll("button").forEach((pastiglia) =>
        pastiglia.addEventListener("click", () => {
          const stato = this._hass.states[pastiglia.dataset.id];
          if (!stato) return;
          this._hass.callService("switch", stato.state === "on" ? "turn_off" : "turn_on", {
            entity_id: pastiglia.dataset.id,
          });
        })
      );
    }
    box.querySelectorAll("button").forEach((pastiglia) => {
      const stato = this._hass.states[pastiglia.dataset.id];
      if (!stato) return;
      pastiglia.classList.toggle("accesa", stato.state === "on");
      pastiglia.classList.toggle("nr", /_banda_n\d/.test(pastiglia.dataset.id));
    });
  }

  /* --- invio -------------------------------------------------------------- */

  async _manda(numero) {
    const box = this.shadowRoot.getElementById("elenco");
    const campo = box.querySelector(`textarea.risposta[data-numero="${numero}"]`);
    const tasto = box.querySelector(`button.manda[data-numero="${numero}"]`);
    const esito = box.querySelector(`.esito[data-numero="${numero}"]`);
    if (!campo) return;
    const testo = campo.value;
    if (!testo.trim()) {
      esito.textContent = "Scrivi qualcosa prima di inviare.";
      return;
    }
    tasto.disabled = true;
    esito.textContent = "Invio in corso...";
    try {
      await this._hass.callService("ha_zyxel", "send_sms", { number: numero, text: testo });
      esito.textContent = "Inviato.";
      campo.value = "";
      if (this._bozze) delete this._bozze[numero];
    } catch (err) {
      esito.textContent = "Non inviato: " + (err && err.message ? err.message : err);
    }
    tasto.disabled = false;
  }

  async _invia() {
    const R = this.shadowRoot;
    const numero = R.getElementById("numero").value.trim();
    const testo = R.getElementById("testo").value;
    const esito = R.getElementById("esito");
    if (!numero || !testo) {
      esito.textContent = "Servono numero e testo.";
      return;
    }
    const tasto = R.getElementById("invia");
    tasto.disabled = true;
    esito.textContent = "Invio in corso...";
    try {
      await this._hass.callService("ha_zyxel", "send_sms", { number: numero, text: testo });
      esito.textContent = "Inviato.";
      R.getElementById("testo").value = "";
    } catch (err) {
      esito.textContent = "Non inviato: " + (err && err.message ? err.message : err);
    }
    tasto.disabled = false;
  }
}

customElements.define("zyxel-panel", PannelloZyxel);
