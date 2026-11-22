/* EnergyPulse AI - one render function per screen.
   Every screen also renders its loading / empty / error states (add ?state=... to the URL;
   states.html lists them all). */
(function () {
  "use strict";
  const EP = window.EP, D = EP.data, F = EP.fmt, esc = EP.esc;
  const P = (EP.pages = {});
  const $ = (sel, root = document) => root.querySelector(sel);

  const diffText = (a) => `${F.signed(a.excess)} kWh <span class="muted">(${F.signed(a.pct)}%)</span>`;
  const headline = (a) => `${F.hours(a.hours)} ${a.direction === "spike" ? "above" : "below"} expected`;

  function loadingBlock(rows) {
    return `<div class="panel panel-pad" aria-busy="true" aria-label="Loading">
      <div class="skel" style="height:22px;width:38%"></div>
      <div class="skel" style="height:${rows ? 14 : 260}px;margin-top:18px"></div>
      ${Array.from({ length: rows || 0 }, () => '<div class="skel" style="height:14px;margin-top:14px"></div>').join("")}
    </div>`;
  }
  function loadError(what) {
    return EP.notice("error", `${what} could not be loaded`,
      "<p>The server did not answer. Nothing was lost. Check your connection and try again.</p>",
      '<a class="btn" href="' + location.pathname.split("/").pop() + '">Try again</a>');
  }

  // ================================================================ Overview
  P.overview = function () {
    const s = EP.settings(), now = EP.parse(D.now);
    const head = (sub) => `<header class="page-head"><div><h1>${esc(s.meterName)}</h1><p class="sub">${sub}</p></div>
      <a class="btn" href="upload.html">${EP.icon.upload}Add readings</a></header>`;

    if (EP.state === "loading") {
      return EP.shell("overview", head("Loading readings") + `<div class="stack">${loadingBlock(0)}<div class="grid-2">${loadingBlock(3)}${loadingBlock(3)}</div></div>`);
    }
    if (EP.state === "error") return EP.shell("overview", head("Readings unavailable") + loadError("Readings"));
    if (EP.state === "empty") {
      return EP.shell("overview", `<header class="page-head"><div><h1>Overview</h1><p class="sub">No meter yet</p></div></header>
        <div class="panel empty"><h2>Add your meter readings to begin</h2>
        <p>Upload a CSV with at least four weeks of readings. You get a forecast for the next 24 hours and an alert whenever consumption is outside the normal range.</p>
        <div class="btn-row"><a class="btn btn-primary" href="upload.html">Add readings</a><a class="btn" href="upload.html?state=sample">Try with a sample file</a></div></div>`);
    }

    const alerts = EP.alerts(), open = alerts.filter((a) => a.status === "needs_review");
    const t = D.today, off = Math.abs(t.pct) >= 5;
    const todayAlert = open.find((a) => EP.parse(a.start).toDateString() === now.toDateString());
    const status = off
      ? `Today is running <b>${Math.round(Math.abs(t.pct))}% ${t.pct > 0 ? "above" : "below"}</b> expected.`
      : `Today is <b>in line</b> with expected.`;
    const meta = `${F.kwh(t.actual)} used by ${F.time(now)}; the forecast for these hours was ${F.kwh(t.expected)}.` +
      (todayAlert ? ` Most of the difference is an alert that started at ${F.time(EP.parse(todayAlert.start))}. <a href="alert.html?id=${todayAlert.id}">Review the alert</a>` : "");
    const n24 = D.next24, peakAt = EP.parse(n24.peakAt), lowAt = EP.parse(n24.lowAt);
    const dayWord = (d) => (d.toDateString() === now.toDateString() ? "today" : "tomorrow");
    const monthCost = D.month.excessKwh * s.tariff;

    const review = open.length
      ? `<ul class="review-list">${open.slice(0, 4).map((a) => `<li><a href="alert.html?id=${a.id}">
            <span class="when">${F.dayTime(EP.parse(a.start))}</span>
            <span class="what">${headline(a)}</span>
            <span class="amount ${a.direction === "spike" ? "up" : "down"}">${F.signed(a.excess)} kWh<small>${a.direction === "spike" ? "about " + F.money(EP.cost(a)) : "no extra cost"}</small></span>
          </a></li>`).join("")}</ul>`
      : `<div class="empty" style="padding:34px 20px"><h2>Nothing to review</h2><p>Every alert has a decision. New alerts appear here as soon as a reading is outside the normal range.</p></div>`;

    EP.shell("overview", head(`Readings up to ${F.dayTime(EP.parse(D.meter.dataTo))}`) + `
      <div class="status-wrap"><div>
        <p class="status-line ${off ? "" : "ok"}">${status}</p>
        <p class="status-meta">${meta}</p>
      </div></div>
      <section class="panel" aria-labelledby="chart-title">
        <div class="panel-head"><h2 id="chart-title">Last 7 days and the next 24 hours</h2><span class="muted small">Hourly readings</span></div>
        <div class="chart-wrap" id="chart"></div>
        ${EP.legend(true)}
      </section>
      <div class="grid-2" style="margin-top:20px">
        <section class="panel" aria-labelledby="review-title">
          <div class="panel-head"><h2 id="review-title">Needs review${open.length ? ` <span class="muted">(${open.length})</span>` : ""}</h2><a href="alerts.html" class="small">All alerts</a></div>
          ${review}
        </section>
        <section class="panel facts" aria-label="Summary">
          <div class="fact"><h3>Next 24 hours</h3><p class="value">${F.num(n24.total)} <small>kWh expected</small></p>
            <p class="note">Highest around ${F.time(peakAt)} ${dayWord(peakAt)} (${F.num(n24.peak)} kWh per hour), lowest around ${F.time(lowAt)} ${dayWord(lowAt)} (${F.num(n24.low)}).</p></div>
          <div class="fact"><h3>Above expected this month</h3><p class="value">${F.num(D.month.excessKwh)} <small>kWh</small></p>
            <p class="note">About ${F.money(monthCost)} at your tariff of ${F.money(s.tariff)} per kWh, from ${D.month.alerts} ${D.month.alerts === 1 ? "alert" : "alerts"}.</p></div>
          <div class="fact"><h3>Forecast accuracy for this meter</h3><p class="value">${F.num(D.accuracy.wape, 1)}% <small>average miss</small></p>
            <p class="note">Measured on all of 2014. Repeating yesterday's reading misses by ${F.num(D.accuracy.baselineWape, 1)}%. <a href="model.html">Model report</a></p></div>
        </section>
      </div>`);
    EP.chart($("#chart"), D.history.concat(D.forecast), { label: "Actual and expected consumption for the last 7 days, with the forecast for the next 24 hours" });
  };

  // ================================================================ Alerts list
  P.alerts = function () {
    const head = `<header class="page-head"><div><h1>Alerts</h1><p class="sub">Readings outside the normal range ${D.alertWindow}</p></div></header>`;
    if (EP.state === "loading") return EP.shell("alerts", head + loadingBlock(6));
    if (EP.state === "error") return EP.shell("alerts", head + loadError("Alerts"));
    if (EP.state === "empty") {
      return EP.shell("alerts", head + `<div class="panel empty"><h2>No alerts ${D.alertWindow}</h2>
        <p>Consumption stayed inside the normal range for every hour. If you expected an alert, you can make detection more sensitive.</p>
        <div class="btn-row"><a class="btn" href="settings.html">Change sensitivity</a></div></div>`);
    }

    const all = EP.alerts();
    const groups = [["needs_review", "Needs review"], ["investigate", "To investigate"], ["expected", "Expected"], ["all", "All"]];
    let current = EP.param("show") || (all.some((a) => a.status === "needs_review") ? "needs_review" : "all");

    function body() {
      const rows = all.filter((a) => current === "all" || a.status === current);
      const tabs = groups.map(([k, label]) => {
        const c = k === "all" ? all.length : all.filter((a) => a.status === k).length;
        return `<button type="button" data-k="${k}" aria-pressed="${k === current}">${label}<span>${c}</span></button>`;
      }).join("");
      if (!rows.length) {
        const msg = current === "needs_review"
          ? ["Nothing to review", "Every alert has a decision. New alerts appear here as soon as a reading is outside the normal range."]
          : ["No alerts with this status", "Alerts move here when you record a decision on them."];
        return `<div class="tabs" role="group" aria-label="Filter by status">${tabs}</div><div class="panel empty"><h2>${msg[0]}</h2><p>${msg[1]}</p></div>`;
      }
      const tr = rows.map((a) => {
        const st = EP.parse(a.start), up = a.direction === "spike";
        return `<tr class="link" data-id="${a.id}">
          <td><a class="row-link" href="alert.html?id=${a.id}">${F.dayTime(st)}</a></td>
          <td>${F.hours(a.hours)}</td>
          <td class="num">${F.num(a.actual)} <span class="muted">of ${F.num(a.expected)} kWh</span></td>
          <td class="num ${up ? "up" : "down"}">${diffText(a)}</td>
          <td class="num">${up ? F.money(EP.cost(a)) : '<span class="muted">None</span>'}</td>
          <td>${EP.severity(a.severity)}</td>
          <td>${EP.badge(a.status)}</td></tr>`;
      }).join("");
      const cards = rows.map((a) => {
        const up = a.direction === "spike";
        return `<li><a href="alert.html?id=${a.id}">
          <div class="top"><strong>${F.dayTime(EP.parse(a.start))}</strong><span class="${up ? "up" : "down"}" style="font-weight:650">${F.signed(a.excess)} kWh</span></div>
          <div class="mid">${headline(a)}${up ? ", about " + F.money(EP.cost(a)) : ""}</div>
          <div class="bottom">${EP.badge(a.status)}${EP.severity(a.severity)}</div></a></li>`;
      }).join("");
      return `<div class="tabs" role="group" aria-label="Filter by status">${tabs}</div>
        <div class="panel">
          <div class="table-wrap swap"><table class="data">
            <thead><tr><th>Started</th><th>Lasted</th><th class="num">Actual of expected</th><th class="num">Difference</th><th class="num">Estimated cost</th><th>Size</th><th>Status</th></tr></thead>
            <tbody>${tr}</tbody></table></div>
          <ul class="alert-cards">${cards}</ul>
        </div>
        <p class="muted small" style="margin-top:12px">Cost uses your tariff of ${F.money(EP.settings().tariff)} per kWh. Readings below expected have no extra cost.</p>`;
    }
    function paint() {
      $("#alerts-body").innerHTML = body();
      document.querySelectorAll(".tabs button").forEach((b) => b.addEventListener("click", () => { current = b.dataset.k; paint(); }));
      document.querySelectorAll("tr.link").forEach((r) => r.addEventListener("click", () => { location.href = "alert.html?id=" + r.dataset.id; }));
    }
    EP.shell("alerts", head + '<div id="alerts-body"></div>');
    paint();
  };

  // ================================================================ Alert detail (investigation)
  const NOTE_MAX = 280;
  P.alert = function () {
    const all = EP.alerts();
    const id = EP.param("id") || (all.find((a) => a.status === "needs_review") || all[0]).id;
    let a = all.find((x) => x.id === id);
    const back = `<a class="back" href="alerts.html">${EP.icon.back}Alerts</a>`;
    if (!a) {
      return EP.shell("alerts", back + `<div class="panel empty"><h2>This alert was not found</h2>
        <p>It may be older than the alerts kept here, or the link is incomplete.</p><div class="btn-row"><a class="btn" href="alerts.html">See all alerts</a></div></div>`);
    }
    if (EP.state === "saved" && a.status === "needs_review") a = Object.assign({}, a, { status: "investigate", note: "Night shift to check which equipment was left running." });

    const s = EP.settings(), st = EP.parse(a.start), en = EP.parse(a.end), up = a.direction === "spike";
    const why = up
      ? `Consumption stayed above the normal range for this meter at ${a.hours === 1 ? "this hour" : "these hours"} for ${F.hours(a.hours)}. The normal range is the forecast plus or minus ${D.report.stdMultiplier} times the usual forecast error of this meter.`
      : `Consumption fell below the normal range for this meter at ${a.hours === 1 ? "this hour" : "these hours"} for ${F.hours(a.hours)}. A drop costs nothing extra, but it can point to equipment that stopped or a meter fault.`;

    function decisionBox() {
      if (a.status !== "needs_review") {
        const label = a.status === "expected" ? "Marked as expected" : "Flagged to investigate";
        return `<section class="decision" aria-labelledby="dec-title">
          <h2 id="dec-title">${label}</h2>
          ${a.note ? `<p class="muted" style="margin-top:8px">Note: ${esc(a.note)}</p>` : '<p class="muted" style="margin-top:8px">No note was added.</p>'}
          <div class="btn-row" style="margin-top:16px"><button class="btn" type="button" id="reopen">Change decision</button></div>
        </section>`;
      }
      return `<section class="decision" aria-labelledby="dec-title">
        <h2 id="dec-title">Was this expected?</h2>
        <p class="muted" style="margin:6px 0 16px">Your answer is saved with the alert, so the next person sees what was decided and why.</p>
        <div class="field" id="note-field">
          <div class="label-row"><label for="note">Note</label><span class="counter" id="note-count">0 / ${NOTE_MAX}</span></div>
          <textarea class="input" id="note" maxlength="400" placeholder="For example: cleaning crew worked overnight" aria-describedby="note-hint note-error"></textarea>
          <p class="hint" id="note-hint">Optional when the reading was expected. Required when you flag it to investigate.</p>
          <p class="error" id="note-error">${EP.icon.error}<span></span></p>
        </div>
        <div class="btn-row full" style="margin-top:18px">
          <button class="btn" type="button" id="mark-expected">Mark as expected</button>
          <button class="btn btn-warn" type="button" id="mark-investigate">Flag to investigate</button>
        </div>
      </section>`;
    }

    EP.shell("alerts", `${back}
      <header class="case-head"><div>
        <h1>${headline(a)}, starting ${F.dayTime(st)}</h1>
        <p style="margin-top:10px;display:flex;gap:14px;align-items:center;flex-wrap:wrap">${EP.badge(a.status)}${EP.severity(a.severity)}${a.holiday ? '<span class="muted small">Public holiday</span>' : ""}</p>
      </div></header>
      <section class="panel" aria-label="Readings around the alert">
        <div class="chart-wrap" id="chart" style="padding-top:14px"></div>
        ${EP.legend(false)}
        <dl class="compare">
          <div><dt>Expected</dt><dd>${F.num(a.expected)} <small>kWh</small></dd></div>
          <div><dt>Actual</dt><dd>${F.num(a.actual)} <small>kWh</small></dd></div>
          <div><dt>Difference</dt><dd class="${up ? "up" : "down"}">${F.signed(a.excess)} <small>kWh (${F.signed(a.pct)}%)</small></dd></div>
        </dl>
      </section>
      <div class="grid-2" style="margin-top:20px">
        <section class="panel panel-pad stack" aria-labelledby="facts-title">
          <h2 id="facts-title">What we know</h2>
          <dl class="detail-list">
            <dt>Started</dt><dd>${F.dayTime(st)}</dd>
            <dt>Back to normal</dt><dd>${F.dayTime(en)}</dd>
            <dt>Normal range at the start</dt><dd>${F.num(a.normalLo)} to ${F.num(a.normalHi)} kWh per hour</dd>
            <dt>Estimated extra cost</dt><dd>${up ? `${F.money(EP.cost(a))} at ${F.money(s.tariff)} per kWh. <a href="settings.html">Change tariff</a>` : "None. Consumption was below expected."}</dd>
            <dt>Public holiday</dt><dd>${a.holiday ? "Yes. Holidays often look unusual and are usually expected." : "No"}</dd>
          </dl>
          <p class="why">${why} This is a deviation to check, not a confirmed fault.</p>
        </section>
        <div id="decision">${decisionBox()}</div>
      </div>`);
    EP.chart($("#chart"), a.series, { height: window.innerWidth < 760 ? 220 : 280, label: "Actual and expected consumption around the alert" });

    function wire() {
      const reopen = $("#reopen");
      if (reopen) {
        reopen.addEventListener("click", () => { EP.undo(a.id); a = Object.assign({}, a, { status: "needs_review", note: "" }); repaint(); });
        return;
      }
      const note = $("#note"), field = $("#note-field"), count = $("#note-count"), err = $("#note-error span");
      const showError = (msg) => { field.classList.add("invalid"); err.textContent = msg; note.setAttribute("aria-invalid", "true"); note.focus(); };
      note.addEventListener("input", () => {
        const n = note.value.trim().length;
        count.textContent = n + " / " + NOTE_MAX;
        count.classList.toggle("over", n > NOTE_MAX);
        if (n <= NOTE_MAX && n > 0) { field.classList.remove("invalid"); note.removeAttribute("aria-invalid"); }
      });
      function decide(status) {
        const text = note.value.trim();
        if (text.length > NOTE_MAX) return showError(`Shorten the note to ${NOTE_MAX} characters. It is ${text.length} now.`);
        if (status === "investigate" && text.length < 3) return showError("Add a note so the person who follows up knows what to check.");
        if (!EP.decide(a.id, status, text)) return showError("The decision could not be saved in this browser. Allow site storage and try again.");
        a = Object.assign({}, a, { status, note: text });
        repaint();
        EP.toast(status === "expected" ? "Marked as expected" : "Flagged to investigate", "Undo", () => { EP.undo(a.id); a = Object.assign({}, a, { status: "needs_review", note: "" }); repaint(); });
      }
      $("#mark-expected").addEventListener("click", () => decide("expected"));
      $("#mark-investigate").addEventListener("click", () => decide("investigate"));
      if (EP.state === "note-error") decide("investigate");
    }
    function repaint() {
      $("#decision").innerHTML = decisionBox();
      const p = $(".case-head p");
      p.innerHTML = EP.badge(a.status) + EP.severity(a.severity) + (a.holiday ? '<span class="muted small">Public holiday</span>' : "");
      wire();
    }
    wire();
    if (EP.state === "saved") EP.toast("Flagged to investigate", "Undo", () => {});
  };

  // ================================================================ Add readings (upload)
  const MAX_MB = 20, MIN_DAYS = 28;
  /* Checks a CSV before it is sent. Returns { errors, warnings, summary, preview }. */
  EP.checkCsv = function (text) {
    const errors = [], warnings = [];
    const lines = text.replace(/^﻿/, "").split(/\r?\n/).filter((l) => l.trim() !== "");
    if (lines.length < 2) return { errors: ["<b>The file is empty.</b> It needs a header row and at least four weeks of readings."], warnings };
    const sep = lines[0].indexOf(";") > -1 && lines[0].indexOf(",") === -1 ? ";" : ",";
    const header = lines[0].split(sep).map((h) => h.trim().toLowerCase().replace(/^"|"$/g, ""));
    const ti = header.indexOf("timestamp"), ki = header.indexOf("kwh");
    if (ti === -1 || ki === -1) {
      const missing = [ti === -1 ? "timestamp" : null, ki === -1 ? "kwh" : null].filter(Boolean).join(" and ");
      return { errors: [`<b>Column ${missing} is missing.</b> The first row must name the columns <span class="mono-ish">timestamp</span> and <span class="mono-ish">kwh</span>. This file has: ${esc(header.join(", ") || "no names")}.`], warnings };
    }
    const re = /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})(?::\d{2})?$/;
    const badDate = [], badNum = [], negative = [], rows = [];
    for (let i = 1; i < lines.length; i++) {
      const c = lines[i].split(sep), m = re.exec((c[ti] || "").trim().replace(/^"|"$/g, ""));
      const raw = (c[ki] || "").trim().replace(/^"|"$/g, "");
      const v = Number(sep === ";" ? raw.replace(",", ".") : raw);
      if (!m) { badDate.push(i + 1); continue; }
      if (raw === "" || !isFinite(v)) { badNum.push(i + 1); continue; }
      if (v < 0) { negative.push(i + 1); continue; }
      rows.push({ t: Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5]), label: m[0].slice(0, 16).replace("T", " "), v });
    }
    const where = (a) => `${a.length === 1 ? "line" : "lines"} ${a.slice(0, 3).join(", ")}${a.length > 3 ? ` and ${a.length - 3} more` : ""}`;
    if (badDate.length) errors.push(`<b>${badDate.length} ${badDate.length === 1 ? "date is" : "dates are"} not readable</b> (${where(badDate)}). Write dates as <span class="mono-ish">2014-06-19 07:00</span>.`);
    if (badNum.length) errors.push(`<b>${badNum.length} ${badNum.length === 1 ? "reading is" : "readings are"} not a number</b> (${where(badNum)}). Leave out the row if the reading is unknown.`);
    if (negative.length) errors.push(`<b>${negative.length} ${negative.length === 1 ? "reading is" : "readings are"} below zero</b> (${where(negative)}). Consumption cannot be negative.`);
    if (!rows.length) return { errors, warnings };

    rows.sort((a, b) => a.t - b.t);
    const uniq = rows.filter((r, i) => i === 0 || r.t !== rows[i - 1].t), dup = rows.length - uniq.length;
    const gaps = uniq.slice(1).map((r, i) => (r.t - uniq[i].t) / 60000).sort((a, b) => a - b);
    const every = gaps.length ? gaps[Math.floor(gaps.length / 2)] : 60;
    if (every !== 15 && every !== 60) errors.push(`<b>Readings must be every 15 minutes or every hour.</b> This file has one about every ${Math.round(every)} minutes.`);
    const days = (uniq[uniq.length - 1].t - uniq[0].t) / 864e5 + every / 1440;
    if (days < MIN_DAYS) errors.push(`<b>Not enough history.</b> The forecast needs at least ${MIN_DAYS} days of readings; this file covers ${Math.floor(days)}.`);
    const expected = Math.round((uniq[uniq.length - 1].t - uniq[0].t) / (every * 60000)) + 1, missing = Math.max(0, expected - uniq.length);
    if (missing / expected > 0.05) errors.push(`<b>Too many readings are missing</b> (${F.num(missing)} of ${F.num(expected)}). Export the file again for a period without long gaps.`);
    else if (missing) warnings.push(`${F.num(missing)} ${missing === 1 ? "reading is" : "readings are"} missing. Each gap is filled with the same hour of the previous day.`);
    if (dup) warnings.push(`${F.num(dup)} repeated ${dup === 1 ? "timestamp was" : "timestamps were"} found. Only the first reading is kept.`);
    if (every === 15) warnings.push("Readings are every 15 minutes. They are added up to hourly totals.");
    const summary = { rows: uniq.length, from: uniq[0].label, to: uniq[uniq.length - 1].label, days: Math.floor(days), every, total: uniq.reduce((s, r) => s + r.v, 0) };
    return { errors, warnings, summary, preview: uniq.slice(0, 5) };
  };

  function brokenSample() {
    const l = D.sampleCsv.trim().split("\n").slice(0, 481);
    l[13] = l[13].split(",")[0] + ",n/a";
    l[76] = l[76].split(",")[0] + ",-12.5";
    l[202] = "25/04/2014 07:00," + l[202].split(",")[1];
    return l.join("\n");
  }

  P.upload = function () {
    const s = EP.settings();
    let step = 1, file = null, check = null, problem = null, progress = 0, failed = false;
    const steps = () => `<ol class="steps" aria-label="Progress">${["Choose a file", "Check and confirm", "Done"].map((t, i) =>
      `<li class="${i + 1 < step ? "done" : i + 1 === step ? "now" : ""}"${i + 1 === step ? ' aria-current="step"' : ""}><span>${t}</span></li>`).join("")}</ol>`;
    const chip = () => `<div class="file-chip">${EP.icon.file}<div><div class="name">${esc(file.name)}</div><div class="meta">${file.size < 1048576 ? F.num(file.size / 1024) + " KB" : F.num(file.size / 1048576, 1) + " MB"}</div></div>
      <button class="btn" type="button" id="reset">Choose a different file</button></div>`;

    function view() {
      if (step === 3) {
        return EP.notice("ok", "Readings added", `<p>${F.num(check.summary.rows)} readings for ${esc(EP.settings().meterName)} are in. The forecast for the next 24 hours is ready.</p>`,
          '<a class="btn btn-primary" href="index.html">Go to overview</a><button class="btn" type="button" id="reset">Add another file</button>');
      }
      if (step === 1) {
        return `${problem ? EP.notice("error", problem.title, problem.body) + '<div style="height:16px"></div>' : ""}
          <div class="grid-2">
            <div class="drop" id="drop">
              <h2>Drop your CSV file here</h2>
              <p>One meter per file, up to ${MAX_MB} MB.</p>
              <div class="btn-row"><label class="btn btn-primary" for="file">Choose a file</label>
                <button class="btn" type="button" id="use-sample">Use the sample file</button></div>
              <input class="sr-only" type="file" id="file" accept=".csv,text/csv">
            </div>
            <section class="panel panel-pad stack" aria-labelledby="req-title">
              <h2 id="req-title">What the file needs</h2>
              <ul class="req">
                <li>Two columns named <code>timestamp</code> and <code>kwh</code></li>
                <li>Dates written as <code>2014-06-19 07:00</code></li>
                <li>One reading every 15 minutes or every hour</li>
                <li>At least ${MIN_DAYS} days of readings, so the forecast can learn the weekly pattern</li>
              </ul>
              <p class="small"><a href="sample/${D.sampleFile}" download>Download a sample file</a> to see the layout.</p>
            </section>
          </div>`;
      }
      // step 2
      if (check.errors.length) {
        return `<div class="stack">${chip()}
          ${EP.notice("error", `This file cannot be used yet: ${check.errors.length} ${check.errors.length === 1 ? "problem" : "problems"} to fix`,
            `<ul>${check.errors.map((e) => `<li>${e}</li>`).join("")}</ul><p style="margin-top:8px">Fix the file and choose it again. Nothing was uploaded.</p>`)}</div>`;
      }
      const m = check.summary;
      const uploading = progress > 0 && !failed;
      return `<div class="grid-2">
        <div class="stack">
          ${chip()}
          ${EP.notice("ok", "The file is ready to upload", `<ul>
            <li><b>${F.num(m.rows)}</b> readings, one every ${m.every === 60 ? "hour" : "15 minutes"}</li>
            <li>From <b>${m.from}</b> to <b>${m.to}</b> (${m.days} days)</li>
            <li>Total consumption <b>${F.kwh(m.total)}</b></li></ul>`)}
          ${check.warnings.length ? EP.notice("warn", "Check before you continue", `<ul>${check.warnings.map((w) => `<li>${w}</li>`).join("")}</ul>`) : ""}
          <section class="panel" aria-labelledby="prev-title"><div class="panel-head"><h2 id="prev-title">First rows</h2></div>
            <div class="table-wrap" style="padding:6px 8px 8px"><table class="data"><thead><tr><th>timestamp</th><th class="num">kwh</th></tr></thead>
            <tbody>${check.preview.map((r) => `<tr><td>${r.label}</td><td class="num">${F.num(r.v, 2)}</td></tr>`).join("")}</tbody></table></div></section>
        </div>
        <form class="panel panel-pad" id="confirm" novalidate>
          <h2 style="margin-bottom:16px">About this meter</h2>
          <div class="field" id="f-name"><label for="name">Meter name</label>
            <input class="input" id="name" value="${esc(s.meterName)}" maxlength="40" autocomplete="off">
            <p class="hint">Shown at the top of the overview.</p><p class="error">${EP.icon.error}<span></span></p></div>
          <div class="field" id="f-tariff"><label for="tariff">Price of one kWh</label>
            <div class="input-row"><input class="input" id="tariff" inputmode="decimal" value="${s.tariff}" autocomplete="off">
              <select class="input" id="currency" aria-label="Currency">${["EUR", "USD", "EGP"].map((c) => `<option${c === s.currency ? " selected" : ""}>${c}</option>`).join("")}</select></div>
            <p class="hint">Used to estimate what unusual consumption costs. You can change it later.</p><p class="error">${EP.icon.error}<span></span></p></div>
          ${failed ? '<div style="margin-top:18px">' + EP.notice("error", "The upload did not finish", "<p>The connection dropped while sending the file. Your file and the details above are still here.</p>") + "</div>" : ""}
          ${uploading ? `<div style="margin-top:20px"><p class="small muted" style="margin-bottom:8px" role="status">Uploading ${esc(file.name)}: ${progress}%</p><div class="progress"><i style="width:${progress}%"></i></div></div>` : ""}
          <div class="btn-row full" style="margin-top:20px"><button class="btn btn-primary" type="submit"${uploading ? " disabled" : ""}>${failed ? "Try again" : uploading ? "Uploading" : "Upload readings"}</button></div>
          <p class="small muted" style="margin-top:14px">Prototype: the file is checked in this browser and is not sent anywhere yet.</p>
        </form></div>`;
    }

    function take(name, size, text) {
      problem = null; progress = 0; failed = false;
      if (!/\.csv$/i.test(name)) {
        const ext = (name.split(".").pop() || "").toLowerCase();
        problem = { title: `${esc(name)} is not a CSV file`, body: `<p>${ext === "xlsx" || ext === "xls" ? "In Excel, choose File, Save as, CSV, then choose the saved file here." : "Export the readings as a .csv file and choose it here."}</p>` };
        step = 1; return paint();
      }
      if (size > MAX_MB * 1048576) {
        problem = { title: `${esc(name)} is larger than ${MAX_MB} MB`, body: "<p>Split the readings into shorter periods, or export hourly readings instead of 15-minute ones.</p>" };
        step = 1; return paint();
      }
      file = { name, size }; check = EP.checkCsv(text); step = 2; paint();
    }
    function setError(id, msg) {
      const f = $(id);
      f.classList.toggle("invalid", !!msg);
      f.querySelector(".error span").textContent = msg || "";
      f.querySelector(".input").toggleAttribute("aria-invalid", !!msg);
      return !msg;
    }
    function paint() {
      $("#upload-body").innerHTML = steps() + view();
      const reset = $("#reset");
      if (reset) reset.addEventListener("click", () => { step = 1; file = check = problem = null; progress = 0; failed = false; paint(); });
      const input = $("#file");
      if (input) {
        const read = (f) => { const r = new FileReader(); r.onload = () => take(f.name, f.size, String(r.result)); r.onerror = () => { problem = { title: "The file could not be read", body: "<p>Close it in other programs and choose it again.</p>" }; paint(); }; r.readAsText(f); };
        input.addEventListener("change", () => input.files[0] && read(input.files[0]));
        const drop = $("#drop");
        ["dragenter", "dragover"].forEach((e) => drop.addEventListener(e, (ev) => { ev.preventDefault(); drop.classList.add("over"); }));
        ["dragleave", "drop"].forEach((e) => drop.addEventListener(e, (ev) => { ev.preventDefault(); drop.classList.remove("over"); }));
        drop.addEventListener("drop", (ev) => ev.dataTransfer.files[0] && read(ev.dataTransfer.files[0]));
        $("#use-sample").addEventListener("click", () => take(D.sampleFile, D.sampleCsv.length, D.sampleCsv));
      }
      const form = $("#confirm");
      if (form) form.addEventListener("submit", (ev) => {
        ev.preventDefault();
        const name = $("#name").value.trim(), t = Number($("#tariff").value.trim().replace(",", "."));
        const okName = setError("#f-name", name ? "" : "Give the meter a name, for example Main building.");
        const okTariff = setError("#f-tariff", !isFinite(t) || t <= 0 ? "Enter the price of one kWh as a number greater than 0, for example 0.15." : t > 100 ? "That is very high for one kWh. Check the price and the currency." : "");
        if (!okName || !okTariff) { (okName ? $("#tariff") : $("#name")).focus(); return; }
        EP.saveSettings({ meterName: name, tariff: t, currency: $("#currency").value });
        failed = false; progress = 4; paint();
        const timer = setInterval(() => {
          progress = Math.min(100, progress + 16);
          const bar = $(".progress i"), label = $('[role="status"]');
          if (bar) bar.style.width = progress + "%";
          if (label) label.textContent = `Uploading ${file.name}: ${progress}%`;
          if (progress >= 100) { clearInterval(timer); step = 3; paint(); }
        }, 260);
      });
    }

    EP.shell("upload", `<header class="page-head"><div><h1>Add readings</h1><p class="sub">Upload the meter's past readings as a CSV file</p></div></header><div id="upload-body"></div>`);
    paint();
    // states for design review
    const st = EP.state;
    if (st === "sample" || st === "ready" || st === "uploading" || st === "failed" || st === "done" || st === "field-errors") take(D.sampleFile, D.sampleCsv.length, D.sampleCsv);
    if (st === "errors") take("meter_export_march.csv", 14800, brokenSample());
    if (st === "wrongtype") take("meter_readings.xlsx", 48200, "");
    if (st === "missing-columns") take("export.csv", 5200, "date;value\n2014-06-19 07:00;120,5\n");
    if (st === "uploading") { progress = 64; paint(); }
    if (st === "failed") { failed = true; paint(); }
    if (st === "done") { step = 3; paint(); }
    if (st === "field-errors") { $("#name").value = ""; $("#tariff").value = "0,15 EUR"; $("#confirm").requestSubmit(); }
  };

  // ================================================================ Model report
  P.model = function () {
    const R = D.report, s = EP.settings();
    const row = (r, cols) => `<tr class="${r.key === "xgb" ? "current" : ""}"><td>${r.key === "xgb" ? "<strong>" + r.label + "</strong>" : r.label}</td>${cols(r)}</tr>`;
    const worst = Math.max(...R.thisMeter.map((r) => r.wape));
    const cells = (r) => `<td class="num">${F.num(r.mae, 2)}</td><td class="num hide-sm">${F.num(r.rmse, 2)}</td><td class="num">${F.num(r.wape, 2)}%</td>
        <td style="width:24%" class="hide-sm"><div class="bar"><i class="${r.key === "xgb" ? "best" : ""}" style="width:${(r.wape / worst) * 100}%"></i></div></td>`;
    const cellsAll = (r) => `<td class="num">${F.num(r.mae, 2)}</td><td class="num hide-sm">${F.num(r.rmse, 2)}</td><td class="num">${F.num(r.wape, 2)}%</td>`;
    const xgb = R.thisMeter.find((r) => r.key === "xgb"), base = R.thisMeter.find((r) => r.key === "baseline");
    const allX = R.allMeters.find((r) => r.key === "xgb"), allB = R.allMeters.find((r) => r.key === "baseline");
    const gain = Math.round((1 - xgb.mae / base.mae) * 100);
    const head = `<thead><tr><th>Method</th><th class="num">Average miss (MAE), kWh</th><th class="num hide-sm">RMSE, kWh</th><th class="num">Share of consumption (WAPE)</th>`;

    EP.shell("model", `<header class="page-head"><div><h1>Model report</h1><p class="sub">How accurate the forecast is, and how alerts are decided</p></div></header>
      <div class="status-wrap"><div>
        <p class="status-line ok">The forecast for ${esc(s.meterName)} misses by <b>${F.num(xgb.wape, 1)}%</b> on average.</p>
        <p class="status-meta">That is ${F.num(xgb.mae, 1)} kWh per hour on a meter that uses about ${F.num(R.meanKwh)} kWh per hour, ${gain}% less error than repeating yesterday's reading. Measured on ${R.testPeriod}, a year the model never saw: it was trained on ${R.trainedOn} and its settings were chosen on ${R.settingsChosenOn}.</p>
      </div></div>
      <div class="stack">
        <section class="panel" aria-labelledby="m1"><div class="panel-head"><h2 id="m1">This meter, forecast one day ahead</h2><span class="muted small">Lower is better</span></div>
          <div class="table-wrap" style="padding:8px 8px 6px"><table class="data">${head}<th class="hide-sm"></th></tr></thead>
            <tbody>${R.thisMeter.map((r) => row(r, cells)).join("")}</tbody></table></div>
          <p class="muted small" style="padding:0 22px 18px;max-width:86ch">The baseline is a simple rule: tomorrow at each hour will be the same as today at that hour. A model is only useful if it beats it.</p>
        </section>
        <section class="panel" aria-labelledby="m2"><div class="panel-head"><h2 id="m2">All ${R.meters} meters</h2><span class="muted small">Average over the meters</span></div>
            <div class="table-wrap" style="padding:8px 8px 6px"><table class="data">${head}</tr></thead>
              <tbody>${R.allMeters.map((r) => row(r, cellsAll)).join("")}</tbody></table></div>
            <p class="muted small" style="padding:0 22px 18px">XGBoost has a lower error than the baseline on ${R.wins} of the ${R.meters} meters (${F.num(allB.wape, 1)}% to ${F.num(allX.wape, 1)}% WAPE). The meters where it does not win are irregular and hard to predict for both.</p>
          </section>
          <section class="panel panel-pad stack" aria-labelledby="m3"><h2 id="m3">How an alert is decided</h2>
            <dl class="detail-list">
              <dt>Usual forecast error</dt><dd>${F.num(R.errorStdKwh, 1)} kWh per hour for this meter (standard deviation, measured on ${R.settingsChosenOn})</dd>
              <dt>Alert when</dt><dd>the reading is more than ${R.stdMultiplier} &times; that, ${F.num(R.thresholdKwh)} kWh, away from the forecast</dd>
              <dt>Hours flagged in 2014</dt><dd>${F.num(R.flaggedHoursPct, 1)}% across all meters, about ${F.num(R.flaggedHoursPerMeterMonth)} hours per meter a month</dd>
              <dt>This meter in 2014</dt><dd>${R.alerts2014.total} alerts, about ${F.num(R.alerts2014.perMonth)} a month</dd>
            </dl>
          </section>
        ${EP.notice("info", "How to read an alert", "<p>An alert means a reading was far from what this meter usually uses at that time. It is a reason to look, not proof of a fault: the dataset has no list of real faults, so the alerts cannot be scored for accuracy. Public holidays often trigger alerts, because the model does not know about them. You mark those as expected in one step.</p>")}
      </div>`);
  };

  // ================================================================ Settings
  P.settings = function () {
    const s = EP.settings(), levels = D.sensitivity.levels;
    const explain = { "Fewer alerts": "Only large deviations", "Standard": "Recommended, the rule used in the model report", "More alerts": "Also smaller deviations, more to review" };
    EP.shell("settings", `<header class="page-head"><div><h1>Settings</h1><p class="sub">Meter details, tariff and alert sensitivity</p></div></header>
      <form id="settings" novalidate style="max-width:640px" class="stack">
        <section class="panel panel-pad"><h2 style="margin-bottom:16px">Meter and tariff</h2>
          <div class="field" id="f-name"><label for="name">Meter name</label>
            <input class="input" id="name" value="${esc(s.meterName)}" maxlength="40" autocomplete="off">
            <p class="hint">Up to 40 characters.</p><p class="error">${EP.icon.error}<span></span></p></div>
          <div class="field" id="f-tariff"><label for="tariff">Price of one kWh</label>
            <div class="input-row"><input class="input" id="tariff" inputmode="decimal" value="${s.tariff}" autocomplete="off">
              <select class="input" id="currency" aria-label="Currency">${["EUR", "USD", "EGP"].map((c) => `<option${c === s.currency ? " selected" : ""}>${c}</option>`).join("")}</select></div>
            <p class="hint">Estimated costs on every alert use this price.</p><p class="error">${EP.icon.error}<span></span></p></div>
        </section>
        <section class="panel panel-pad"><h2>Alert sensitivity</h2>
          <p class="muted" style="margin:4px 0 16px">How far a reading must be from expected before it becomes an alert.</p>
          <div class="choices" role="radiogroup" aria-label="Alert sensitivity">${levels.map((l) => `<label class="choice">
            <input type="radio" name="sens" value="${l.label}"${l.label === s.sensitivity ? " checked" : ""}>
            <strong>${l.label}</strong><small>${explain[l.label]}</small>
            <span class="per"><b>${F.num(l.alertsPerMonth)}</b>alerts a month</span></label>`).join("")}</div>
          <p class="hint small muted" style="margin-top:12px">Alerts a month is what each level would have produced for this meter in 2014.</p>
        </section>
        <div class="btn-row full"><button class="btn btn-primary" type="submit">Save changes</button><button class="btn" type="button" id="clear">Clear saved review decisions</button></div>
      </form>`);
    function setError(id, msg) {
      const f = $(id);
      f.classList.toggle("invalid", !!msg);
      f.querySelector(".error span").textContent = msg || "";
      f.querySelector(".input").toggleAttribute("aria-invalid", !!msg);
      return !msg;
    }
    $("#settings").addEventListener("submit", (ev) => {
      ev.preventDefault();
      const name = $("#name").value.trim(), t = Number($("#tariff").value.trim().replace(",", "."));
      const okName = setError("#f-name", name ? "" : "Give the meter a name, for example Main building.");
      const okTariff = setError("#f-tariff", !isFinite(t) || t <= 0 ? "Enter the price of one kWh as a number greater than 0, for example 0.15." : t > 100 ? "That is very high for one kWh. Check the price and the currency." : "");
      if (!okName || !okTariff) { (okName ? $("#tariff") : $("#name")).focus(); return; }
      const ok = EP.saveSettings({ meterName: name, tariff: t, currency: $("#currency").value, sensitivity: document.querySelector('input[name="sens"]:checked').value });
      EP.toast(ok ? "Changes saved" : "Changes could not be saved in this browser");
    });
    $("#clear").addEventListener("click", () => { EP.saveSettings({ decisions: {} }); EP.toast("Review decisions cleared"); });
    if (EP.state === "errors") { $("#name").value = ""; $("#tariff").value = "abc"; $("#settings").requestSubmit(); }
    if (EP.state === "saved") EP.toast("Changes saved");
  };

  // ================================================================ Index of screens and states
  P.states = function () {
    function alertStates() {
      const all = D.alerts, open = all.find((a) => a.status === "needs_review") || all[0];
      const out = [[`alert.html?id=${open.id}`, "Open alert"], [`alert.html?id=${open.id}&state=note-error`, "Note required"],
        [`alert.html?id=${open.id}&state=saved`, "Decision saved"]];
      const drop = all.find((a) => a.direction === "drop" && a.holiday) || all.find((a) => a.direction === "drop");
      if (drop) out.push([`alert.html?id=${drop.id}`, drop.holiday ? "Below expected, public holiday" : "Below expected"]);
      const decided = all.find((a) => a.status !== "needs_review");
      if (decided) out.push([`alert.html?id=${decided.id}`, "Decision already recorded"]);
      out.push(["alert.html?id=none", "Alert not found"]);
      return out;
    }
    const groups = [
      ["Overview", [["index.html", "With data"], ["index.html?state=empty", "First run, no readings"], ["index.html?state=loading", "Loading"], ["index.html?state=error", "Readings could not be loaded"]]],
      ["Add readings", [["upload.html", "Choose a file"], ["upload.html?state=ready", "File checked and ready"], ["upload.html?state=errors", "File with problems"], ["upload.html?state=wrongtype", "Wrong file type"], ["upload.html?state=missing-columns", "Columns missing"], ["upload.html?state=field-errors", "Form errors"], ["upload.html?state=uploading", "Uploading"], ["upload.html?state=failed", "Upload failed"], ["upload.html?state=done", "Done"]]],
      ["Alerts", [["alerts.html", "Needs review"], ["alerts.html?show=all", "All alerts"], ["alerts.html?show=investigate", "To investigate"], ["alerts.html?state=empty", "No alerts"], ["alerts.html?state=loading", "Loading"], ["alerts.html?state=error", "Alerts could not be loaded"]]],
      ["Alert review", alertStates()],
      ["Model report", [["model.html", "Results"]]],
      ["Settings", [["settings.html", "Form"], ["settings.html?state=errors", "Form errors"], ["settings.html?state=saved", "Saved"]]],
    ];
    EP.shell("", `<header class="page-head"><div><h1>Screens and states</h1><p class="sub">Every screen in the main flow, with its loading, empty and error states</p></div></header>
      <div class="stack">${groups.map(([g, items]) => `<section class="panel panel-pad"><h2 style="margin-bottom:10px">${g}</h2>
        <ul class="req" style="columns:2;column-gap:32px">${items.map(([href, label]) => `<li><a href="${href}">${label}</a></li>`).join("")}</ul></section>`).join("")}</div>`);
  };

  document.addEventListener("DOMContentLoaded", () => {
    const page = document.body.dataset.page;
    if (P[page]) P[page]();
  });
})();
