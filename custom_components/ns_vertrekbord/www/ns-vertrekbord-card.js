/*
 * ns-vertrekbord-card  v1.1.0
 * Lovelace card that shows an "NS vertrekbord" sensor as a Dutch station departure board:
 * minutes to departure, train type, destination, via stations, track (changes in red),
 * delay, cancellation, NS messages and the next train.
 *
 *   type: custom:ns-vertrekbord-card
 *   entity: sensor.utrecht_leidsche_rijn_utrecht_centraal_vertrek_over
 *   compact: false
 */
(() => {
  const VERSION = "1.1.0";
  const TAG = "ns-vertrekbord-card";
  const BAD = new Set(["unavailable", "unknown", undefined, null, ""]);
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  // keep names like 's-Hertogenbosch / Driebergen-Zeist on one line
  const nb = (s) => esc(String(s ?? "").replace(/-/g, "‑").replace(/^'s/, "’s"));
  const CATS = { SPR: "Sprinter", IC: "Intercity", ICD: "Intercity direct", ICE: "ICE", EST: "Eurostar", NSI: "Internationaal", ST: "Stoptrein", SNT: "Sneltrein" };

  const T = {
    nl: { min: "minuten", min1: "minuut", now: "Vertrekt nu", track: "Spoor", was: "was", dep: "vertrek", from: "vanaf", via: "via", and: "en",
      cancelled: "Rijdt niet", next: "Volgende trein", after: "Daarna", none: "Geen vertrekken", offline: "Geen gegevens", pick: "Kies een NS vertrekbord-sensor" },
    en: { min: "minutes", min1: "minute", now: "Departing now", track: "Track", was: "was", dep: "departs", from: "from", via: "via", and: "and",
      cancelled: "Cancelled", next: "Next train", after: "Then", none: "No departures", offline: "No data", pick: "Choose an NS departure board sensor" },
  };

  const CSS = `
    :host { display:block; --nsb-blue:#23356b; --nsb-red:#c8102e; --nsb-yellow:#fff3c4; --nsb-amber:#f2b300; }
    ha-card { padding:12px; container-type:inline-size; overflow:hidden; }
    .board { background:#fff; border-radius:6px; overflow:hidden; color:var(--nsb-blue); cursor:pointer;
      font-family:Frutiger,"Myriad Pro","Segoe UI",Arial,sans-serif; box-shadow:0 0 0 5px #3a3f45, 0 0 0 6px #000; margin:6px; }
    .in { padding:clamp(10px,3cqi,16px) clamp(12px,3.6cqi,18px) 8px; }
    .top { display:flex; justify-content:space-between; align-items:flex-start; gap:10px; }
    .mins { font-weight:700; line-height:1; white-space:nowrap; }
    .mins b { font-size:clamp(34px,13cqi,62px); } .mins span { font-size:clamp(17px,6.2cqi,30px); margin-left:6px; }
    .type { font-weight:700; font-size:clamp(22px,8cqi,40px); line-height:1.05; white-space:nowrap; }
    .meta { display:flex; flex-wrap:wrap; gap:8px; align-items:center; margin-top:6px; font-size:clamp(12px,3.4cqi,16px); font-weight:700; }
  .meta .from { font-weight:600; opacity:.7; }
    .spoor { background:var(--nsb-blue); color:#fff; border-radius:4px; padding:2px 8px; }
    .spoor.chg { background:var(--nsb-red); }
    .late { color:var(--nsb-red); }
    .dest { font-weight:700; line-height:1.2; padding-bottom:.06em; margin-top:4px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
    .via { font-weight:700; font-size:clamp(14px,4.6cqi,23px); line-height:1.3; margin-top:4px; }
    .rem { margin-top:8px; background:var(--nsb-yellow); border-left:5px solid var(--nsb-amber); padding:6px 10px; font-weight:700; font-size:clamp(12px,3.4cqi,16px); }
    .cancel { color:var(--nsb-red); font-weight:700; font-size:clamp(18px,5.4cqi,26px); margin-top:4px; }
    .strike { text-decoration:line-through; text-decoration-thickness:3px; color:#9aa6c0; }
    .bar { background:var(--nsb-blue); color:#fff; font-weight:700; font-size:clamp(13px,4.4cqi,22px); padding:8px clamp(12px,3.6cqi,18px); }
    .empty { padding:18px; font-weight:700; font-size:18px; }
    .warn { padding:8px; color:var(--error-color,#db4437); }
  `;

  class NSVertrekbordCard extends HTMLElement {
    static getStubConfig(hass) {
      const e = Object.keys(hass?.states || {}).find((id) => id.startsWith("sensor.") && Array.isArray(hass.states[id].attributes?.departures)
        && "station_code" in hass.states[id].attributes);
      return { entity: e || "" };
    }

    static getConfigForm() {
      return {
        schema: [
          { name: "entity", required: true, selector: { entity: { domain: "sensor", integration: "ns_vertrekbord" } } },
          { type: "grid", name: "", flatten: true, schema: [
            { name: "compact", selector: { boolean: {} } },
            { name: "show_via", selector: { boolean: {} } },
            { name: "show_messages", selector: { boolean: {} } },
            { name: "show_track", selector: { boolean: {} } },
            { name: "show_station", selector: { boolean: {} } },
          ] },
          { name: "next_count", selector: { number: { min: 0, max: 3, step: 1, mode: "slider" } } },
          { name: "type_style", selector: { select: { mode: "dropdown", options: [
            { value: "auto", label: "Automatisch (Sprinter / SPR in compact)" }, { value: "long", label: "Voluit (Sprinter)" }, { value: "short", label: "Kort (SPR)" }] } } },
          { name: "language", selector: { select: { mode: "dropdown", options: [{ value: "nl", label: "Nederlands" }, { value: "en", label: "English" }] } } },
        ],
        computeLabel: (s) => ({
          entity: "Vertrekbord (sensor 'Vertrek over')", compact: "Compacte variant", show_via: "Via-stations tonen",
          show_messages: "NS-berichten tonen", show_track: "Spoor tonen", show_station: "Vertrekstation tonen", next_count: "Volgende treinen in de onderbalk",
          type_style: "Treinsoort", language: "Taal",
        }[s.name] ?? s.name),
        computeHelper: (s) => ({ compact: "Zonder via-regel, kleiner lettertype; handig voor smalle kolommen." }[s.name]),
      };
    }

    setConfig(config) {
      if (!config) throw new Error("Invalid configuration");
      this._config = { compact: false, show_via: true, show_messages: true, show_track: true, show_station: true, next_count: null, type_style: "auto", language: "nl", ...config };
      this._lang = String(this._config.language).startsWith("en") ? "en" : "nl";
      this._last = null;
      if (this._hass) this._render();
    }
    set hass(hass) { this._hass = hass; this._render(); }
    connectedCallback() { this._tick = setInterval(() => { this._last = null; this._render(); }, 15000); }
    disconnectedCallback() { clearInterval(this._tick); }
    getCardSize() { return this._config?.compact ? 3 : 5; }
    getGridOptions() { return { columns: this._config?.compact ? 6 : 12, rows: "auto", min_columns: 4 }; }
    t(k) { return T[this._lang][k] ?? k; }

    _mins(dep) {
      const at = Date.parse(dep.actual || dep.planned || "");
      return isNaN(at) ? null : Math.max(0, Math.floor((at - Date.now()) / 60000));
    }
    _hm(iso) {
      const d = new Date(iso);
      return isNaN(d) ? "" : d.toLocaleTimeString(this._hass.locale?.language || "nl", { hour: "2-digit", minute: "2-digit" });
    }
    _type(dep, compact) {
      const s = this._config.type_style;
      const short = s === "short" || (s === "auto" && compact);
      return short ? dep.category || "" : CATS[dep.category] || dep.category_name || dep.category || "";
    }
    _viaText(list) {
      const v = (list || []).filter(Boolean);
      if (!v.length) return "";
      const names = v.map(nb);
      return `${this.t("via")} ${names.length > 1 ? names.slice(0, -1).join(", ") + ` ${this.t("and")} ` + names[names.length - 1] : names[0]}`;
    }

    _render() {
      if (!this._config || !this._hass) return;
      if (!this.shadowRoot) {
        this.attachShadow({ mode: "open" });
        this.shadowRoot.addEventListener("click", () => {
          if (this._config.entity) this.dispatchEvent(new CustomEvent("hass-more-info", { bubbles: true, composed: true, detail: { entityId: this._config.entity } }));
        });
      }
      const c = this._config, st = this._hass.states[c.entity];
      let html;
      if (!c.entity) html = `<div class="warn">${this.t("pick")}</div>`;
      else if (!st) html = `<div class="warn">${esc(c.entity)}?</div>`;
      else html = this._board(st);
      if (html !== this._last) { this.shadowRoot.innerHTML = `<style>${CSS}</style><ha-card>${html}</ha-card>`; this._last = html; }
    }

    _board(st) {
      const c = this._config, t = (k) => this.t(k), compact = !!c.compact;
      const now = Date.now() - 30000;
      const deps = BAD.has(st.state) && !Array.isArray(st.attributes.departures) ? [] :
        (st.attributes.departures || []).filter((d) => Date.parse(d.actual || d.planned || "") >= now);
      if (!deps.length) {
        return `<div class="board"><div class="empty">${BAD.has(st.state) ? t("offline") : t("none")}</div>
          <div class="bar">${nb(st.attributes.station || "")}</div></div>`;
      }
      const d = deps[0], m = this._mins(d), cx = d.cancelled;
      const minHtml = m === 0 && !cx ? `<b style="font-size:clamp(26px,9cqi,44px)">${t("now")}</b>`
        : `<b>${m}</b><span>${m === 1 ? t("min1") : t("min")}</span>`;
      const len = String(d.direction || "").length;
      const destSize = compact ? `clamp(22px,${len > 16 ? 7 : 9}cqi,40px)` : `clamp(26px,${len > 18 ? 8 : len > 13 ? 9.5 : 12}cqi,58px)`;
      const trackTxt = d.track_changed ? `${t("track")} ${esc(d.track)} (${t("was")} ${esc(d.planned_track)})` : `${t("track")} ${esc(d.track || "–")}`;
      const meta = `<div class="meta">${c.show_track && d.track ? `<span class="spoor${d.track_changed ? " chg" : ""}">${trackTxt}</span>` : ""}
        <span>${compact ? "" : t("dep") + " "}${this._hm(d.planned)}${d.delay_minutes > 0 ? ` <span class="late">+${d.delay_minutes}</span>` : ""}</span>${!compact && c.show_station !== false && st.attributes.station ? `<span class="from">${t("from")} ${esc(st.attributes.station)}</span>` : ""}</div>`;
      const via = !compact && c.show_via ? this._viaText(d.via) : "";
      const msgs = c.show_messages ? (d.messages || []) : [];

      // bottom bar: next running train(s) after the one shown
      const nCount = c.next_count ?? (compact ? 2 : 1);
      const rest = deps.slice(1).filter((x) => !x.cancelled).slice(0, nCount);
      let bar = "";
      if (nCount > 0 && rest.length) {
        const item = (x) => `${this._hm(x.actual || x.planned)} ${esc(x.category || "")} ${nb(x.direction)}`;
        if (cx) bar = `${t("next")}: ${item(rest[0])} (${this._mins(rest[0])} min)`;
        else if (rest.length === 1) bar = `${t("next")}: ${item(rest[0])}`;
        else bar = `${t("after")}: ${rest.map(item).join(" · ")}`;
      }

      return `<div class="board"><div class="in">
          <div class="top"><div class="mins${cx ? " strike" : ""}">${minHtml}</div><div class="type">${esc(this._type(d, compact))}</div></div>
          ${compact ? "" : meta}
          <div class="dest${cx ? " strike" : ""}" style="font-size:${destSize}">${nb(d.direction)}</div>
          ${compact ? meta : ""}
          ${cx ? `<div class="cancel">${t("cancelled")}</div>` : ""}
          ${via ? `<div class="via">${via}</div>` : ""}
          ${msgs.map((x) => `<div class="rem">${esc(x)}</div>`).join("")}
        </div>${bar ? `<div class="bar">${bar}</div>` : ""}</div>`;
    }
  }

  if (!customElements.get(TAG)) {
    customElements.define(TAG, NSVertrekbordCard);
    window.customCards = window.customCards || [];
    window.customCards.push({ type: TAG, name: "NS Vertrekbord Card",
      description: "NS vertrekbord sensor as a Dutch station departure board.", preview: true });
    console.info(`%c NS-VERTREKBORD-CARD %c v${VERSION} `, "background:#23356b;color:#fff", "background:#fff;color:#23356b");
  }
})();
