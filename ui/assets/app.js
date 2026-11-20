/* EnergyPulse AI - shared interface code (no framework, no build step).
   Data comes from assets/data.js, which is exported from the trained model
   by ml/src/export_ui_data.py. Connecting to the live API is the next milestone. */
(function () {
  "use strict";
  const D = window.EP_DATA;
  const EP = (window.EP = {});
  EP.data = D;
  EP.state = new URLSearchParams(location.search).get("state") || "";
  EP.param = (k) => new URLSearchParams(location.search).get(k);

  // ------------------------------------------------------------ dates and numbers
  const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const pad = (n) => String(n).padStart(2, "0");
  EP.parse = function (s) {
    const [d, t] = s.split("T");
    const [y, m, dd] = d.split("-").map(Number);
    const [h, mi] = (t || "00:00").split(":").map(Number);
    return new Date(y, m - 1, dd, h, mi);
  };
  const SYMBOL = { EUR: "€", USD: "$", EGP: "EGP " };
  EP.fmt = {
    num: (v, d = 0) => Number(v).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d }),
    kwh: (v, d = 0) => EP.fmt.num(v, d) + " kWh",
    time: (dt) => pad(dt.getHours()) + ":" + pad(dt.getMinutes()),
    day: (dt) => DAYS[dt.getDay()] + " " + dt.getDate() + " " + MONTHS[dt.getMonth()],
    dayTime: (dt) => EP.fmt.day(dt) + ", " + EP.fmt.time(dt),
    range: (a, b) => EP.fmt.dayTime(a) + " to " + (a.toDateString() === b.toDateString() ? EP.fmt.time(b) : EP.fmt.dayTime(b)),
    hours: (n) => n + (n === 1 ? " hour" : " hours"),
    money: (v) => (SYMBOL[EP.settings().currency] || "") + EP.fmt.num(v, 2),
    signed: (v, d = 0) => (v > 0 ? "+" : v < 0 ? "−" : "") + EP.fmt.num(Math.abs(v), d),
  };
  EP.esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  // ------------------------------------------------------------ saved choices (this browser only)
  const KEY = "energypulse.prototype.v1";
  function read() {
    try { return JSON.parse(localStorage.getItem(KEY)) || {}; } catch (e) { return {}; }
  }
  function write(s) {
    try { localStorage.setItem(KEY, JSON.stringify(s)); return true; } catch (e) { return false; }
  }
  EP.settings = function () {
    const s = read();
    return {
      tariff: s.tariff != null ? s.tariff : D.tariff.value,
      currency: s.currency || D.tariff.currency,
      sensitivity: s.sensitivity || "Standard",
      meterName: s.meterName || D.meter.name,
    };
  };
  EP.saveSettings = (patch) => write(Object.assign(read(), patch));
  EP.alerts = function () {
    const dec = read().decisions || {};
    return D.alerts.map((a) => Object.assign({}, a, dec[a.id] || {}));
  };
  EP.decide = function (id, status, note) {
    const s = read();
    s.decisions = s.decisions || {};
    s.decisions[id] = { status, note, demo: false };
    return write(s);
  };
  EP.undo = function (id) {
    const s = read();
    if (s.decisions) delete s.decisions[id];
    return write(s);
  };
  EP.cost = (a) => Math.max(a.excess, 0) * EP.settings().tariff;

  // ------------------------------------------------------------ icons
  const I = (p, extra = "") => `<svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" ${extra}>${p}</svg>`;
  EP.icon = {
    overview: I('<path d="M2.5 13.5l4-5 3.5 3 4-6.5 3.5 4"/><path d="M2.5 17h15"/>'),
    alerts: I('<path d="M10 3.2l7.3 12.6H2.7L10 3.2z"/><path d="M10 8.3v3.6"/><circle cx="10" cy="14" r=".4" fill="currentColor"/>'),
    upload: I('<path d="M10 13V3.5"/><path d="M6.2 7.2L10 3.4l3.8 3.8"/><path d="M3.5 12.5v3a1 1 0 001 1h11a1 1 0 001-1v-3"/>'),
    model: I('<path d="M3.5 16.5v-5"/><path d="M8 16.5v-9"/><path d="M12.5 16.5V10"/><path d="M17 16.5V4"/>'),
    settings: I('<path d="M3 6h8"/><path d="M15 6h2"/><circle cx="13" cy="6" r="2"/><path d="M3 14h2"/><path d="M9 14h8"/><circle cx="7" cy="14" r="2"/>'),
    back: I('<path d="M12 4.5L6.5 10l5.5 5.5"/>'),
    error: I('<circle cx="10" cy="10" r="7.3"/><path d="M10 6.3v4.4"/><circle cx="10" cy="13.4" r=".4" fill="currentColor"/>'),
    ok: I('<circle cx="10" cy="10" r="7.3"/><path d="M6.6 10.2l2.3 2.3 4.5-4.8"/>'),
    info: I('<circle cx="10" cy="10" r="7.3"/><path d="M10 9.2v4.4"/><circle cx="10" cy="6.6" r=".4" fill="currentColor"/>'),
    file: I('<path d="M5 2.8h6.2L15 6.6v10.6H5V2.8z"/><path d="M11 2.8v4h4"/>'),
  };
  const MARK = '<svg width="28" height="28" viewBox="0 0 28 28" aria-hidden="true"><rect width="28" height="28" rx="7" fill="#142b3d"/><path d="M4.5 15h4l2.2-6.5 3.6 12 2.6-8 1.4 2.5h5.2" fill="none" stroke="#54e5c5" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';

  // ------------------------------------------------------------ page shell
  const NAV = [
    ["overview", "index.html", "Overview", "Overview"],
    ["alerts", "alerts.html", "Alerts", "Alerts"],
    ["upload", "upload.html", "Add readings", "Add"],
    ["model", "model.html", "Model report", "Model"],
    ["settings", "settings.html", "Settings", "Settings"],
  ];
  EP.shell = function (page, html) {
    const open = EP.alerts().filter((a) => a.status === "needs_review").length;
    const hideCount = EP.state === "empty" || EP.state === "loading";
    const now = EP.parse(D.now);
    const nav = NAV.map(([id, href, label, short]) => {
      const cur = id === page ? ' aria-current="page"' : "";
      const count = id === "alerts" && open && !hideCount ? `<span class="count" aria-label="${open} alerts need review">${open}</span>` : "";
      return `<a href="${href}"${cur}>${EP.icon[id]}<span class="label"><span class="long">${label}</span><span class="short" hidden>${short}</span></span>${count}</a>`;
    }).join("");
    document.getElementById("app").innerHTML = `
      <div class="app">
        <aside class="rail">
          <a class="brand" href="index.html">${MARK}<span class="brand-name">Energy<span>Pulse</span></span></a>
          <nav class="nav" aria-label="Main">${nav}</nav>
          <div class="rail-foot"><strong>Prototype workspace</strong>Readings, forecasts and alerts come from the trained model on UCI meter ${D.meter.id}. The clock is set to ${EP.fmt.dayTime(now)}, 2014.<br><a href="states.html">All screens and states</a></div>
        </aside>
        <main class="main" id="main">
          <div class="topbar">${MARK}<span class="brand-name">Energy<span style="color:var(--mint)">Pulse</span></span></div>
          ${html}
        </main>
      </div>`;
    // short labels in the mobile tab bar
    const mq = window.matchMedia("(max-width: 759px)");
    const swap = () => document.querySelectorAll(".nav .label").forEach((l) => {
      l.querySelector(".long").hidden = mq.matches;
      l.querySelector(".short").hidden = !mq.matches;
    });
    swap();
    mq.addEventListener("change", swap);
  };

  EP.toast = function (text, undoLabel, onUndo) {
    document.querySelectorAll(".toast").forEach((t) => t.remove());
    const t = document.createElement("div");
    t.className = "toast";
    t.setAttribute("role", "status");
    t.innerHTML = `<span>${EP.esc(text)}</span>` + (undoLabel ? `<button type="button">${EP.esc(undoLabel)}</button>` : "");
    document.body.appendChild(t);
    if (undoLabel) t.querySelector("button").addEventListener("click", () => { t.remove(); onUndo(); });
    if (EP.state !== "saved") setTimeout(() => t.remove(), 6000);
  };

  EP.badge = function (status) {
    const map = { needs_review: ["review", "Needs review"], expected: ["expected", "Expected"], investigate: ["investigate", "To investigate"] };
    const [cls, label] = map[status] || map.needs_review;
    return `<span class="badge badge-${cls}">${label}</span>`;
  };
  EP.severity = function (sev) {
    const n = { low: 1, medium: 2, high: 3 }[sev] || 1;
    const label = { low: "Small", medium: "Medium", high: "Large" }[sev];
    return `<span class="sev" title="Size of the deviation">${[1, 2, 3].map((i) => `<i class="${i <= n ? "on" : ""}"></i>`).join("")} ${label}</span>`;
  };
  EP.notice = function (kind, title, body, actions) {
    const ic = { error: "error", warn: "error", ok: "ok", info: "info" }[kind];
    return `<div class="notice notice-${kind}" role="${kind === "error" ? "alert" : "status"}">${EP.icon[ic]}<h3>${title}</h3>${body || ""}${actions ? `<div class="btn-row">${actions}</div>` : ""}</div>`;
  };

  // ------------------------------------------------------------ chart
  function niceStep(raw) {
    const p = Math.pow(10, Math.floor(Math.log10(raw)));
    const f = raw / p;
    return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * p;
  }
  /* pts: [{t, actual|null, expected, lo, hi, flag}]  -  actual === null marks the forecast part */
  EP.chart = function (el, pts, opt = {}) {
    let lastW = 0;
    const tip = document.createElement("div");
    tip.className = "tip";
    tip.hidden = true;
    const holder = document.createElement("div");
    holder.className = "chart";
    el.innerHTML = "";
    el.append(holder, tip);
    const times = pts.map((p) => EP.parse(p.t));

    function draw() {
      const W = Math.max(280, Math.floor(el.clientWidth - 18));
      if (W === lastW) return;
      lastW = W;
      const narrow = W < 520;
      const H = opt.height || (narrow ? 230 : 320);
      const m = { l: 44, r: 10, t: 22, b: 30 };
      const iw = W - m.l - m.r, ih = H - m.t - m.b, n = pts.length;
      const vals = [];
      pts.forEach((p) => { [p.actual, p.expected, p.lo, p.hi].forEach((v) => v != null && vals.push(v)); });
      let lo = Math.min(...vals), hi = Math.max(...vals);
      const step = niceStep((hi - lo) / 4);
      lo = Math.floor(lo / step) * step;
      hi = Math.ceil(hi / step) * step;
      const x = (i) => m.l + (n === 1 ? 0 : (i / (n - 1)) * iw);
      const y = (v) => m.t + ih - ((v - lo) / (hi - lo)) * ih;
      const line = (key, from, to) => {
        let d = "", pen = false;
        for (let i = from; i <= to; i++) {
          const v = pts[i][key];
          if (v == null) { pen = false; continue; }
          d += (pen ? "L" : "M") + x(i).toFixed(1) + " " + y(v).toFixed(1);
          pen = true;
        }
        return d;
      };
      const firstFc = pts.findIndex((p) => p.actual == null);
      const lastActual = firstFc === -1 ? n - 1 : firstFc - 1;
      let s = `<svg viewBox="0 0 ${W} ${H}" height="${H}" role="img" aria-label="${EP.esc(opt.label || "Actual and expected consumption per hour")}">`;

      // forecast region
      if (firstFc > 0) {
        const fx = x(firstFc - 0.5);
        s += `<rect x="${fx}" y="${m.t}" width="${m.l + iw - fx}" height="${ih}" fill="rgba(69,169,250,0.07)"/>`;
      }
      // flagged hours: shade the energy between expected and actual
      const colW = Math.max(iw / Math.max(n - 1, 1), 2);
      let excess = "";
      for (let i = 0; i < n; i++) {
        if (!pts[i].flag || pts[i].actual == null) continue;
        let j = i;
        while (j + 1 < n && pts[j + 1].flag && pts[j + 1].actual != null) j++;
        const x0 = Math.max(m.l, x(i) - colW / 2), x1 = Math.min(m.l + iw, x(j) + colW / 2);
        let d = `M${x0.toFixed(1)} ${y(pts[i].actual).toFixed(1)}`;
        for (let k = i; k <= j; k++) d += `L${x(k).toFixed(1)} ${y(pts[k].actual).toFixed(1)}`;
        d += `L${x1.toFixed(1)} ${y(pts[j].actual).toFixed(1)}L${x1.toFixed(1)} ${y(pts[j].expected).toFixed(1)}`;
        for (let k = j; k >= i; k--) d += `L${x(k).toFixed(1)} ${y(pts[k].expected).toFixed(1)}`;
        d += `L${x0.toFixed(1)} ${y(pts[i].expected).toFixed(1)}Z`;
        excess += `<path d="${d}" fill="rgba(255,165,104,0.38)"/>`;
        i = j;
      }
      // horizontal grid and y labels
      for (let v = lo; v <= hi + 1e-9; v += step) {
        s += `<line x1="${m.l}" x2="${m.l + iw}" y1="${y(v)}" y2="${y(v)}" stroke="#162c3e"/>`;
        s += `<text x="${m.l - 8}" y="${y(v) + 4}" text-anchor="end">${EP.fmt.num(v)}</text>`;
      }
      s += `<text x="${m.l - 36}" y="12">kWh per hour</text>`;
      // x labels
      const spanH = n;
      const everyDay = spanH > 60;
      const skip = everyDay ? (narrow ? 2 : 1) : 1;
      let dayCount = 0;
      times.forEach((t, i) => {
        const h = t.getHours();
        if (everyDay) {
          if (h !== 0) return;
          s += `<line x1="${x(i)}" x2="${x(i)}" y1="${m.t}" y2="${m.t + ih}" stroke="#162c3e"/>`;
          if (dayCount++ % skip === 0 && x(i) < m.l + iw - 30) s += `<text x="${x(i) + 4}" y="${H - 9}">${DAYS[t.getDay()]} ${t.getDate()}</text>`;
        } else if (h % (narrow ? 12 : 6) === 0) {
          s += `<line x1="${x(i)}" x2="${x(i)}" y1="${m.t}" y2="${m.t + ih}" stroke="#162c3e"/>`;
          const lab = h === 0 ? DAYS[t.getDay()] + " " + t.getDate() : EP.fmt.time(t);
          if (x(i) < m.l + iw - 26) s += `<text x="${x(i) + 4}" y="${H - 9}" ${h === 0 ? 'fill="#a2b5c4"' : ""}>${lab}</text>`;
        }
      });
      // normal range band
      let band = "";
      pts.forEach((p, i) => { band += (i ? "L" : "M") + x(i).toFixed(1) + " " + y(p.hi).toFixed(1); });
      for (let i = n - 1; i >= 0; i--) band += "L" + x(i).toFixed(1) + " " + y(pts[i].lo).toFixed(1);
      s += `<path d="${band}Z" fill="rgba(84,229,197,0.13)"/>`;
      s += excess;
      // expected: solid for the past, dashed for the forecast
      s += `<path d="${line("expected", 0, lastActual)}" fill="none" stroke="#54e5c5" stroke-width="1.8" stroke-linejoin="round"/>`;
      if (firstFc > 0) s += `<path d="${line("expected", lastActual, n - 1)}" fill="none" stroke="#54e5c5" stroke-width="1.8" stroke-dasharray="5 4"/>`;
      // actual
      s += `<path d="${line("actual", 0, lastActual)}" fill="none" stroke="#f4faff" stroke-width="1.8" stroke-linejoin="round"/>`;
      pts.forEach((p, i) => {
        if (p.flag && p.actual != null) s += `<circle cx="${x(i).toFixed(1)}" cy="${y(p.actual).toFixed(1)}" r="4" fill="#ffa568" stroke="#081420" stroke-width="1.5"/>`;
      });
      // "now" marker
      if (firstFc > 0) {
        const fx = x(firstFc - 0.5);
        s += `<line x1="${fx}" x2="${fx}" y1="${m.t - 6}" y2="${m.t + ih}" stroke="#45a9fa" stroke-width="1.2"/>`;
        s += `<text x="${fx - 6}" y="${m.t - 9}" text-anchor="end" fill="#45a9fa">Now</text>`;
        if (!narrow) s += `<text x="${fx + 6}" y="${m.t - 9}" fill="#45a9fa">Forecast</text>`;
      }
      s += `<line class="cursor" x1="0" x2="0" y1="${m.t}" y2="${m.t + ih}" stroke="#a2b5c4" stroke-width="1" visibility="hidden"/>`;
      s += `<rect class="hit" x="${m.l}" y="${m.t}" width="${iw}" height="${ih}" fill="transparent"/></svg>`;
      holder.innerHTML = s;

      const hit = holder.querySelector(".hit"), cursor = holder.querySelector(".cursor");
      hit.addEventListener("mousemove", (ev) => {
        const r = hit.getBoundingClientRect();
        const i = Math.max(0, Math.min(n - 1, Math.round(((ev.clientX - r.left) / r.width) * (n - 1))));
        const p = pts[i];
        cursor.setAttribute("x1", x(i)); cursor.setAttribute("x2", x(i)); cursor.setAttribute("visibility", "visible");
        const diff = p.actual != null ? p.actual - p.expected : null;
        tip.innerHTML = `<strong>${EP.fmt.dayTime(times[i])}</strong>` +
          (p.actual != null ? `<div class="row">Actual <b>${EP.fmt.kwh(p.actual, 1)}</b></div>` : "") +
          `<div class="row">${p.actual != null ? "Expected" : "Forecast"} <b>${EP.fmt.kwh(p.expected, 1)}</b></div>` +
          `<div class="row">Normal range <b>${EP.fmt.num(p.lo)} to ${EP.fmt.num(p.hi)}</b></div>` +
          (diff != null ? `<div class="row">Difference <b style="color:${p.flag ? "#ffa568" : "inherit"}">${EP.fmt.signed(diff, 1)} kWh</b></div>` : "") +
          (p.flag ? `<div style="color:#ffa568;font-weight:600;margin-top:2px">Outside the normal range</div>` : "");
        tip.hidden = false;
        const er = el.getBoundingClientRect();
        let left = ev.clientX - er.left + 14;
        if (left + 190 > er.width) left = ev.clientX - er.left - 190;
        tip.style.left = left + "px";
        tip.style.top = Math.max(8, ev.clientY - er.top - 20) + "px";
      });
      hit.addEventListener("mouseleave", () => { tip.hidden = true; cursor.setAttribute("visibility", "hidden"); });
    }
    draw();
    if (window.ResizeObserver) new ResizeObserver(draw).observe(el);
    else window.addEventListener("resize", draw);
  };

  EP.legend = function (withForecast) {
    return `<div class="legend">
      <span><i class="key"></i>Actual</span>
      <span><i class="key key-expected"></i>Expected</span>
      <span><i class="key key-band"></i>Normal range for that hour</span>
      <span><i class="key key-flag"></i>Outside the normal range</span>
      ${withForecast ? '<span><i class="key key-forecast"></i>Forecast, next 24 hours</span>' : ""}
    </div>`;
  };
})();
