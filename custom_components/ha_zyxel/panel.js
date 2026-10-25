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
  input[type=text], input[type=password], select, textarea {
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
  .dettaglio { display:flex; justify-content:space-between; gap:12px; font-size:13px;
               color:var(--secondary-text-color); margin-bottom:4px; }
  .dettaglio b { font-weight:500; color:var(--primary-text-color); }
  .campo { display:flex; flex-direction:column; gap:5px; margin-bottom:10px; }
  .campo input { width:100%; box-sizing:border-box; padding:13px 14px;
                 border-radius:10px; font-size:15px; }
  .riga-int { display:flex; align-items:center; justify-content:space-between;
              gap:12px; margin-bottom:14px; }
  /* Interruttore disegnato a mano: la pastiglia non si capiva che fosse
     cliccabile, e <ha-switch> dentro uno shadow root non e' garantito. */
  .interruttore { position:relative; flex:none; width:42px; height:22px; padding:0;
                  border:none; border-radius:999px; cursor:pointer;
                  background:var(--switch-unchecked-track-color,#8d8d8d);
                  transition:background .2s; }
  .interruttore::after { content:''; position:absolute; top:2px; left:2px;
                         width:18px; height:18px; border-radius:50%;
                         background:#fff; transition:left .2s;
                         box-shadow:0 1px 3px rgba(0,0,0,.4); }
  .interruttore.acceso { background:var(--primary-color,#03a9f4); }
  .interruttore.acceso::after { left:22px; }
  .con-occhio { position:relative; }
  .con-occhio input { padding-right:48px; }
  .occhio { position:absolute; right:6px; top:50%; transform:translateY(-50%);
            background:none; border:none; cursor:pointer; padding:5px;
            line-height:0; color:var(--secondary-text-color); opacity:.7;
            --mdc-icon-size:24px; }
  .occhio:hover { opacity:1; }
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
        <div class="scheda" id="scheda-wifi" hidden>
          <h2>Wi-Fi del router</h2>
          <div class="riga-int">
            <span>Radio Wi-Fi <span class="etichetta" id="wifi-stato"></span></span>
            <button class="interruttore" id="wifi-radio" role="switch"
                    aria-label="Accendi o spegni il Wi-Fi"></button>
          </div>
          <div class="dettaglio"><span>Banda</span><b id="wifi-banda">—</b></div>
          <div class="dettaglio"><span>Canale</span><b id="wifi-canale">—</b></div>
          <div class="dettaglio"><span>Sicurezza</span><b id="wifi-sicurezza">—</b></div>
          <div style="border-top:1px solid var(--divider-color,#e0e0e0);
                      margin:14px 0 12px"></div>
          <div class="campo">
            <span class="etichetta">Nome rete (SSID)</span>
            <input type="text" id="wifi-nome" autocomplete="off">
          </div>
          <div class="campo">
            <span class="etichetta">Password</span>
            <div class="con-occhio">
              <input type="password" id="wifi-password" autocomplete="new-password"
                     placeholder="almeno 8 caratteri">
              <button class="occhio" id="wifi-occhio" aria-label="Mostra la password">
                <ha-icon icon="mdi:eye-outline"></ha-icon>
              </button>
            </div>
          </div>
          <button class="azione" id="wifi-salva">Salva</button>
          <div class="nota" id="wifi-esito">Al salvataggio la rete si riavvia: i
            dispositivi collegati si staccano e devono riconnettersi.</div>
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
    this.shadowRoot.getElementById("wifi-radio").addEventListener("click", () => {
      const ent = this._uno("switch.", "wi_fi");
      if (!ent) return;
      this._hass.callService("switch", ent.state === "on" ? "turn_off" : "turn_on", {
        entity_id: ent.entity_id,
      });
    });
    this.shadowRoot.getElementById("wifi-occhio").addEventListener("click", () => {
      const campo = this.shadowRoot.getElementById("wifi-password");
      const nascosta = campo.type === "password";
      campo.type = nascosta ? "text" : "password";
      this.shadowRoot
        .getElementById("wifi-occhio")
        .firstElementChild.setAttribute(
          "icon",
          nascosta ? "mdi:eye-off-outline" : "mdi:eye-outline"
        );
      campo.focus();
    });
    this.shadowRoot
      .getElementById("wifi-salva")
      .addEventListener("click", () => this._salvaWifi());
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
    this._wifi();
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

  /* --- Wi-Fi -------------------------------------------------------------- */

  _wifi() {
    const R = this.shadowRoot;
    const scheda = R.getElementById("scheda-wifi");
    const ent = this._uno("switch.", "wi_fi");
    if (!ent) {
      scheda.hidden = true;
      return;
    }
    scheda.hidden = false;

    const a = ent.attributes || {};
    const acceso = ent.state === "on";
    const interruttore = R.getElementById("wifi-radio");
    interruttore.classList.toggle("acceso", acceso);
    interruttore.setAttribute("aria-checked", acceso ? "true" : "false");
    R.getElementById("wifi-stato").textContent = acceso ? "accesa" : "spenta";
    R.getElementById("wifi-banda").textContent = a.banda || "—";
    R.getElementById("wifi-canale").textContent =
      a.canale === 0 || a.canale === "0" ? "automatico" : a.canale || "—";
    R.getElementById("wifi-sicurezza").textContent = a.sicurezza || "—";

    // La chiave attuale si chiede al router una volta sola, cosi' il campo non
    // e' mai vuoto e l'occhio ha qualcosa da mostrare. Non arriva dallo stato
    // delle entita': la da' un servizio, su richiesta.
    if (!this._passwordChiesta) {
      this._passwordChiesta = true;
      this._caricaPassword();
    }

    // Il nome lo riempie il router, ma non mentre l'utente ci sta scrivendo:
    // ogni giro del coordinator gli cancellerebbe quello che ha digitato.
    const nome = R.getElementById("wifi-nome");
    if (!this._ascoltoNome) {
      nome.addEventListener("input", () => { this._nomeToccato = true; });
      this._ascoltoNome = true;
    }
    if (!this._nomeToccato && R.activeElement !== nome) {
      nome.value = a.nome_rete || "";
    }
  }

  async _caricaPassword() {
    const campo = this.shadowRoot.getElementById("wifi-password");
    try {
      const risposta = await this._hass.callService(
        "ha_zyxel",
        "leggi_password_wifi",
        {},
        undefined,
        false,
        true
      );
      const chiave = risposta && risposta.response ? risposta.response.password : "";
      if (chiave && !campo.value) campo.value = chiave;
      this._passwordInVigore = chiave;
    } catch (err) {
      // Non e' grave: il campo resta vuoto e si comporta come prima.
      this._passwordChiesta = false;
    }
  }

  async _salvaWifi() {
    const R = this.shadowRoot;
    const nome = R.getElementById("wifi-nome").value.trim();
    const password = R.getElementById("wifi-password").value;
    const esito = R.getElementById("wifi-esito");
    const bottone = R.getElementById("wifi-salva");
    const ent = this._uno("switch.", "wi_fi");
    const attuale = ent && ent.attributes ? ent.attributes.nome_rete || "" : "";

    const dati = {};
    if (nome && nome !== attuale) dati.nome = nome;
    if (password && password !== this._passwordInVigore) {
      if (password.length < 8) {
        esito.textContent = "La password WPA2 vuole almeno 8 caratteri.";
        return;
      }
      dati.password = password;
    }
    if (!Object.keys(dati).length) {
      esito.textContent = "Niente da cambiare.";
      return;
    }

    bottone.disabled = true;
    esito.textContent = "Scrivo sul router...";
    try {
      await this._hass.callService("ha_zyxel", "imposta_wifi", dati);
      // Il campo resta pieno: e' la chiave in vigore, non una bozza da buttare.
      R.getElementById("wifi-password").type = "password";
      R.getElementById("wifi-occhio").firstElementChild.setAttribute(
        "icon",
        "mdi:eye-outline"
      );
      this._nomeToccato = false;
      if (dati.password) this._passwordInVigore = dati.password;
      esito.textContent = "Fatto. Ricollega i dispositivi.";
    } catch (err) {
      esito.textContent = "Non riuscito: " + (err && err.message ? err.message : err);
    } finally {
      bottone.disabled = false;
    }
  }
}
customElements.define("zyxel-panel", PannelloZyxel);
