// PromptCheck UI: a hash-routed single page over the JSON API. No build step, no dependencies.
"use strict";

const app = document.getElementById("app");
const ticker = document.getElementById("ticker");
let renderToken = 0;      // drops renders that finish after the user has navigated away
let pollTimer = null;

// ---------- helpers ----------

// Every value from the API goes through esc() before it reaches put().
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => (
  { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function put(el, html) {
  el.replaceChildren(document.createRange().createContextualFragment(html));
}

async function api(path, options = {}) {
  const init = { method: options.method || "GET", headers: {} };
  if (options.body !== undefined) {
    init.headers["content-type"] = "application/json";
    init.body = JSON.stringify(options.body);
  }
  let resp;
  try {
    resp = await fetch(path, init);
  } catch {
    throw new Error("Can't reach the PromptCheck server. Is it still running?");
  }
  if (resp.status === 204) return null;
  const data = await resp.json().catch(() => null);
  if (!resp.ok) throw new Error(errorText(data, resp.status));
  return data;
}

function errorText(data, code) {
  const detail = data && data.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    // Pydantic validation errors: name the field and the problem
    return detail.map((d) => `${(d.loc || []).filter((p) => p !== "body").join(".") || "request"}: ${d.msg}`).join("; ");
  }
  return `The server answered ${code}.`;
}

function toast(message, bad = false) {
  ticker.textContent = message;
  ticker.classList.toggle("bad", bad);
  ticker.classList.add("show");
  clearTimeout(toast.t);
  toast.t = setTimeout(() => ticker.classList.remove("show"), bad ? 6000 : 3200);
}

const pct = (rate) => (rate === null || rate === undefined ? "—" : `${Math.round(rate * 1000) / 10}%`);
const pad = (n, w = 4) => String(n).padStart(w, "0");
const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;

function when(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

const icon = {
  plus: '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 2.5v11M2.5 8h11" stroke="currentColor" stroke-width="2" fill="none"/></svg>',
  play: '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M4.5 2.8v10.4L13 8z" fill="currentColor"/></svg>',
  arrow: '<svg viewBox="0 0 34 16" aria-hidden="true"><path d="M1 8h29M23 2l7 6-7 6" stroke="currentColor" stroke-width="2.4" fill="none"/></svg>',
  redo: '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M12.5 5.5A5 5 0 1 0 13 9" stroke="currentColor" stroke-width="2" fill="none"/><path d="M13.5 1.8v4h-4" stroke="currentColor" stroke-width="2" fill="none"/></svg>',
  box: '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M2 5h12v8.5H2zM1.5 2.5h13V5h-13zM6 8h4" stroke="currentColor" stroke-width="1.6" fill="none"/></svg>',
  swap: '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M2 5h11M10 2l3 3-3 3M14 11H3M6 8l-3 3 3 3" stroke="currentColor" stroke-width="1.8" fill="none"/></svg>',
};

// Code 39: a real, scannable barcode drawn from the parcel's id (n = narrow, w = wide)
const CODE39 = {
  "0": "nnnwwnwnn", "1": "wnnwnnnnw", "2": "nnwwnnnnw", "3": "wnwwnnnnn", "4": "nnnwwnnnw",
  "5": "wnnwwnnnn", "6": "nnwwwnnnn", "7": "nnnwnnwnw", "8": "wnnwnnwnn", "9": "nnwwnnwnn",
  A: "wnnnnwnnw", B: "nnwnnwnnw", C: "wnwnnwnnn", D: "nnnnwwnnw", E: "wnnnwwnnn", F: "nnwnwwnnn",
  G: "nnnnnwwnw", H: "wnnnnwwnn", I: "nnwnnwwnn", J: "nnnnwwwnn", K: "wnnnnnnww", L: "nnwnnnnww",
  M: "wnwnnnnwn", N: "nnnnwnnww", O: "wnnnwnnwn", P: "nnwnwnnwn", Q: "nnnnnnwww", R: "wnnnnnwwn",
  S: "nnwnnnwwn", T: "nnnnwnwwn", U: "wwnnnnnnw", V: "nwwnnnnnw", W: "wwwnnnnnn", X: "nwnnwnnnw",
  Y: "wwnnwnnnn", Z: "nwwnwnnnn", "-": "nwnnnnwnw", ".": "wwnnnnwnn", " ": "nwwnnnwnn", "*": "nwnnwnwnn",
};

function barcode(text) {
  const chars = `*${text.toUpperCase()}*`.split("").filter((c) => CODE39[c]);
  let x = 0;
  let bars = "";
  for (const c of chars) {
    CODE39[c].split("").forEach((e, i) => {
      const w = e === "w" ? 3 : 1;
      if (i % 2 === 0) bars += `<rect x="${x}" y="0" width="${w}" height="40"/>`;
      x += w;
    });
    x += 1; // inter-character gap
  }
  return `<span class="barcode" aria-hidden="true"><svg viewBox="0 0 ${x} 40" preserveAspectRatio="none" fill="currentColor">${bars}</svg><span class="barcode-text">*${esc(text.toUpperCase())}*</span></span>`;
}

function meter(rate, hold = false) {
  if (rate === null || rate === undefined) return '<span class="muted">Not run yet</span>';
  const w = Math.max(0, Math.min(1, rate)) * 100;
  return `<span class="meter${hold ? " is-hold" : ""}"><span class="meter-track" role="img" aria-label="Pass rate ${pct(rate)}"><span class="meter-fill" style="width:${w}%"></span></span><span class="meter-val">${pct(rate)}</span></span>`;
}

// the API says "ship" / "block"; on the dock a blocked parcel is on HOLD
function stamp(verdict, href) {
  if (!verdict) return '<span class="stamp none">No gate yet</span>';
  const tag = href ? "a" : "span";
  const attr = href ? ` href="${href}"` : "";
  const hold = verdict === "block";
  return `<${tag} class="stamp ${hold ? "hold" : "ship"}"${attr} title="verdict: ${esc(verdict)}">${hold ? "Hold" : "Ship"}</${tag}>`;
}

const status = (s) => `<span class="st ${esc(s)}">${esc(s)}</span>`;

const templateHtml = (t) => esc(t).replace(/\{(\w+)\}/g, '<span class="var">{$1}</span>');

function loading(text = "Printing label") {
  put(app, `<div class="sheet"><div class="loading">${esc(text)}</div></div>`);
}

function errorSheet(message) {
  put(app, `<div class="sheet"><div class="empty"><strong>Label can't be printed</strong><p class="err">${esc(message)}</p><a class="btn ghost" href="#/">Back to the manifest</a></div></div>`);
}

function crumbs(items) {
  return `<nav class="crumbs" aria-label="Breadcrumb">${items.map((it, i) =>
    (i ? '<span aria-hidden="true">/</span>' : "") + (it.href ? `<a href="${it.href}">${esc(it.label)}</a>` : `<span aria-current="page">${esc(it.label)}</span>`)).join("")}</nav>`;
}

function busy(button, on) {
  if (!button) return;
  button.setAttribute("aria-busy", on ? "true" : "false");
  button.disabled = on;
}

function formError(form, message) {
  let box = form.querySelector(".err");
  if (!message) { box?.remove(); return; }
  if (!box) {
    box = document.createElement("p");
    box.className = "err";
    box.setAttribute("role", "alert");
    form.querySelector(".form-actions").before(box);
  }
  put(box, `<b>Not saved.</b> ${esc(message)}`);
}

// a drawer is an inline panel (no modal): the toggle button owns aria-expanded
function drawer(scope, toggleSel, panelSel, cancelSel, focusEl) {
  const panel = scope.querySelector(panelSel);
  const toggle = scope.querySelector(toggleSel);
  const setOpen = (open) => {
    panel.hidden = !open;
    toggle.setAttribute("aria-expanded", String(open));
    if (open) focusEl?.focus();
  };
  toggle.onclick = () => setOpen(panel.hidden);
  scope.querySelector(cancelSel).onclick = () => { setOpen(false); toggle.focus(); };
  return setOpen;
}

// ---------- router ----------

function route() {
  clearTimeout(pollTimer);
  const token = ++renderToken;
  const parts = location.hash.replace(/^#\/?/, "").split("/").filter(Boolean);
  document.querySelectorAll("[data-nav]").forEach((a) =>
    (parts.length === 0 ? a.setAttribute("aria-current", "page") : a.removeAttribute("aria-current")));
  const go = { p: viewPrompt, r: viewRun, c: viewCompare }[parts[0]];
  const view = go ? go(token, ...parts.slice(1)) : viewManifest(token);
  view.catch((e) => { if (token === renderToken) errorSheet(e.message); });
}

window.addEventListener("hashchange", () => { route(); app.focus({ preventScroll: true }); window.scrollTo(0, 0); });
document.addEventListener("DOMContentLoaded", route);

// ---------- manifest (all prompts) ----------

async function viewManifest(token) {
  loading("Printing the manifest");
  const [prompts, runs] = await Promise.all([api("/prompts"), api("/runs")]);
  // each prompt's gate = its latest completed run compared with the one before it
  const rows = await Promise.all(prompts.map(async (p) => {
    const done = runs.filter((r) => r.prompt_id === p.id && r.status === "completed");
    const active = runs.some((r) => r.prompt_id === p.id && (r.status === "pending" || r.status === "running"));
    const gate = done.length >= 2
      ? await api(`/runs/compare?base=${done[1].id}&candidate=${done[0].id}`).catch(() => null)
      : null;
    return { p, last: done[0], gate, active };
  }));
  if (token !== renderToken) return;
  const held = rows.filter((r) => r.gate?.verdict === "block").length;

  put(app, `
    <section class="sheet" aria-labelledby="m-title">
      <div class="sheet-head">
        <div>
          <h1 class="sheet-title" id="m-title">Manifest</h1>
          <p class="sheet-note">${plural(prompts.length, "prompt")} on the dock${held ? ` · <b>${held} on hold</b>` : ""}. Each gate compares a prompt's latest run with the run before it.</p>
        </div>
        <button class="btn" type="button" id="new-toggle" aria-expanded="false" aria-controls="new-prompt">${icon.plus}New prompt</button>
      </div>
      <div class="drawer-body" id="new-prompt" hidden>
        <form class="form" id="new-form" novalidate>
          <div class="form-row">
            <label class="f"><span>Name</span><input type="text" name="name" required maxlength="100" placeholder="order-status-reply" autocomplete="off"></label>
            <label class="f"><span>Description</span><input type="text" name="description" placeholder="What this prompt does in production"></label>
          </div>
          <div class="form-actions"><button class="btn" type="submit">Create prompt</button><button class="btn quiet" type="button" id="new-cancel">Cancel</button></div>
        </form>
      </div>
      ${prompts.length ? `
      <table class="manifest">
        <thead><tr><th scope="col">Route</th><th scope="col">Prompt</th><th scope="col">Cases</th><th scope="col">Last run</th><th scope="col">Gate</th><th scope="col" class="cell-code">Parcel</th></tr></thead>
        <tbody>${rows.map(({ p, last, gate, active }) => {
          const hold = gate?.verdict === "block";
          return `<tr class="${hold ? "is-hold" : ""}">
            <td class="cell-route"><span class="route-sm${p.latest_version ? "" : " none"}">${p.latest_version ? `V${p.latest_version}` : "V—"}</span></td>
            <td><a class="p-name" href="#/p/${p.id}">${esc(p.name)}</a>${p.description ? `<span class="p-desc">${esc(p.description)}</span>` : ""}</td>
            <td class="cell-cases" data-label="Cases"><span class="num">${p.test_case_count ?? 0}</span> <span class="muted">active</span></td>
            <td class="cell-bar" data-label="Last run">${active ? status("running") : meter(last?.pass_rate, hold)}${last ? `<span class="p-desc">run #${last.id} · v${last.version}</span>` : ""}</td>
            <td class="cell-gate" data-label="Gate">${stamp(gate?.verdict, gate ? `#/c/${gate.base_run_id}/${gate.candidate_run_id}` : null)}</td>
            <td class="cell-code">${barcode(`PC-${pad(p.id)}`)}</td>
          </tr>`;
        }).join("")}</tbody>
      </table>` : `
      <div class="empty"><strong>The dock is empty</strong><p>Create a prompt, publish a version and add test cases. Then run it.</p></div>`}
    </section>`);

  const form = document.getElementById("new-form");
  drawer(app, "#new-toggle", "#new-prompt", "#new-cancel", form.name);
  form.onsubmit = async (ev) => {
    ev.preventDefault();
    const name = form.name.value.trim();
    if (!name) { formError(form, "Give the prompt a name."); form.name.focus(); return; }
    const btn = form.querySelector("[type=submit]");
    busy(btn, true);
    try {
      const p = await api("/prompts", { method: "POST", body: { name, description: form.description.value.trim() } });
      toast(`Prompt ${p.name} created`);
      location.hash = `#/p/${p.id}`;
    } catch (e) {
      formError(form, e.message);
    } finally { busy(btn, false); }
  };
}

// ---------- one prompt: versions, runs, test cases ----------

async function viewPrompt(token, id) {
  loading();
  const [prompt, versions, cases, runs, checks] = await Promise.all([
    api(`/prompts/${id}`), api(`/prompts/${id}/versions`), api(`/prompts/${id}/test-cases`),
    api(`/runs?prompt_id=${id}`), api("/checks"),
  ]);
  if (token !== renderToken) return;
  const latest = versions[versions.length - 1];

  put(app, `
    ${crumbs([{ label: "Manifest", href: "#/" }, { label: prompt.name }])}
    <section class="sheet" aria-labelledby="p-title">
      <div class="parcel">
        <div class="parcel-main">
          <h1 class="parcel-name" id="p-title">${esc(prompt.name)}</h1>
          ${prompt.description ? `<p class="parcel-desc">${esc(prompt.description)}</p>` : ""}
        </div>
        <div class="parcel-code">
          <span class="route">${latest ? `V${latest.version}` : "V—"}</span>
          ${barcode(`PC-${pad(prompt.id)}${latest ? `-V${latest.version}` : ""}`)}
        </div>
      </div>
      <dl class="fields">
        <div class="field"><dt>Prompt id</dt><dd>${prompt.id}</dd></div>
        <div class="field"><dt>Versions</dt><dd>${versions.length}</dd></div>
        <div class="field"><dt>Active cases</dt><dd>${cases.length}</dd></div>
        <div class="field"><dt>Runs</dt><dd>${runs.length}</dd></div>
        <div class="field"><dt>Created</dt><dd>${when(prompt.created_at)}</dd></div>
      </dl>
    </section>
    <div id="versions"></div>
    <div id="runs"></div>
    <div id="cases"></div>`);

  renderVersions(token, prompt, versions, cases);
  renderRuns(token, prompt, runs);
  renderCases(prompt, cases, latest, checks);
}

function renderVersions(token, prompt, versions, cases) {
  const box = document.getElementById("versions");
  const latest = versions[versions.length - 1];
  put(box, `
    <section class="sheet" aria-labelledby="v-title">
      <div class="sheet-head">
        <div>
          <h2 class="sheet-title" id="v-title">Versions</h2>
          <p class="sheet-note">A published version never changes. To edit, publish the next one.</p>
        </div>
        <button class="btn ghost" type="button" id="pub-toggle" aria-expanded="false" aria-controls="pub">${icon.plus}Publish version</button>
      </div>
      <div class="drawer-body" id="pub" hidden>
        <form class="form" id="pub-form" novalidate>
          <label class="f"><span>Template · use {variable} for inputs</span><textarea name="template" required spellcheck="false">${esc(latest?.template || "")}</textarea></label>
          <div class="form-row">
            <label class="f"><span>Model (optional)</span><input type="text" name="model" placeholder="Server default" value="${esc(latest?.model || "")}"></label>
            <label class="f"><span>Notes</span><input type="text" name="notes" placeholder="What changed and why"></label>
          </div>
          <div class="form-actions"><button class="btn" type="submit">Publish v${(latest?.version || 0) + 1}</button><button class="btn quiet" type="button" id="pub-cancel">Cancel</button></div>
        </form>
      </div>
      ${versions.length ? `
      <div class="sheet-body">
        <p class="hint" style="margin:0 0 8px">Latest template, v${latest.version}</p>
        <pre class="tpl">${templateHtml(latest.template)}</pre>
      </div>
      <table class="ledger">
        <thead><tr><th scope="col">Ver.</th><th scope="col">Notes</th><th scope="col">Variables</th><th scope="col">Model</th><th scope="col">Published</th><th scope="col">Actions</th></tr></thead>
        <tbody>${[...versions].reverse().map((v) => `
          <tr>
            <td><span class="v">V${v.version}</span></td>
            <td data-label="Notes">${v.notes ? esc(v.notes) : '<span class="muted">—</span>'}</td>
            <td data-label="Variables">${v.variables.length ? v.variables.map((n) => `<span class="kv">{${esc(n)}}</span>`).join("") : '<span class="muted">none</span>'}</td>
            <td data-label="Model">${v.model ? `<code>${esc(v.model)}</code>` : '<span class="muted">default</span>'}</td>
            <td data-label="Published">${when(v.created_at)}</td>
            <td class="actions">
              ${v.version > 1 ? `<button class="btn sm ghost" type="button" data-diff="${v.version}">Diff v${v.version - 1}</button>` : ""}
              <button class="btn sm" type="button" data-run="${v.id}" data-v="${v.version}" ${cases.length ? "" : 'disabled title="Add a test case first"'}>${icon.play}Run v${v.version}</button>
            </td>
          </tr>`).join("")}
        </tbody>
      </table>
      ${versions.length > 1 ? `
      <div class="sheet-foot">
        <form class="form-actions" id="diff-form">
          <label class="f"><span>From</span><select name="a">${versions.map((v) => `<option value="${v.version}" ${v.version === latest.version - 1 ? "selected" : ""}>v${v.version}</option>`).join("")}</select></label>
          <label class="f"><span>To</span><select name="b">${versions.map((v) => `<option value="${v.version}" ${v.version === latest.version ? "selected" : ""}>v${v.version}</option>`).join("")}</select></label>
          <button class="btn ghost" type="submit" style="align-self:end">Show diff</button>
        </form>
        <div id="diff-out"></div>
      </div>` : ""}` : `
      <div class="empty"><strong>No versions yet</strong><p>Publish the first version of this prompt's template.</p></div>`}
    </section>`);

  const form = box.querySelector("#pub-form");
  const setOpen = drawer(box, "#pub-toggle", "#pub", "#pub-cancel", form.template);
  if (!versions.length) setOpen(true);
  form.onsubmit = async (ev) => {
    ev.preventDefault();
    if (!form.template.value.trim()) { formError(form, "The template can't be empty."); return; }
    const btn = form.querySelector("[type=submit]");
    busy(btn, true);
    try {
      const v = await api(`/prompts/${prompt.id}/versions`, { method: "POST", body: {
        template: form.template.value, model: form.model.value.trim() || null, notes: form.notes.value.trim(),
      } });
      toast(`Published v${v.version}`);
      route();
    } catch (e) { formError(form, e.message); } finally { busy(btn, false); }
  };

  box.querySelectorAll("[data-run]").forEach((b) => { b.onclick = async () => {
    busy(b, true);
    try {
      const run = await api("/runs", { method: "POST", body: { prompt_version_id: Number(b.dataset.run) } });
      toast(`Run #${run.id} started for v${b.dataset.v}`);
      const runs = await api(`/runs?prompt_id=${prompt.id}`);
      if (token === renderToken) renderRuns(token, prompt, runs);
    } catch (e) { toast(e.message, true); } finally { busy(b, false); }
  }; });

  const diffForm = box.querySelector("#diff-form");
  const showDiff = async (a, b) => {
    const out = box.querySelector("#diff-out");
    put(out, '<div class="loading">Comparing</div>');
    try {
      const d = await api(`/prompts/${prompt.id}/versions/${a}/diff/${b}`);
      const lines = d.diff.filter((l) => !l.startsWith("---") && !l.startsWith("+++"));
      put(out, `
        <p class="hint" style="margin:14px 0 8px">v${esc(a)} → v${esc(b)}: <b>+${d.added}</b> / <b>−${d.removed}</b> lines${d.model_changed ? " · model changed" : ""}</p>
        ${lines.length ? `<pre class="diff">${lines.map((l) => {
          const cls = l.startsWith("@@") ? "hunk" : l[0] === "+" ? "add" : l[0] === "-" ? "del" : "";
          return `<div class="${cls}">${esc(cls === "hunk" ? l : l.slice(1))}</div>`;
        }).join("")}</pre>` : '<p class="hint">The templates are identical.</p>'}`);
    } catch (e) { put(out, `<p class="err">${esc(e.message)}</p>`); }
  };
  if (diffForm) diffForm.onsubmit = (ev) => { ev.preventDefault(); showDiff(diffForm.a.value, diffForm.b.value); };
  box.querySelectorAll("[data-diff]").forEach((b) => { b.onclick = () => {
    const v = Number(b.dataset.diff);
    diffForm.a.value = v - 1;
    diffForm.b.value = v;
    showDiff(v - 1, v);
    diffForm.scrollIntoView({ behavior: "smooth", block: "center" });
  }; });
}

function renderRuns(token, prompt, runs) {
  const box = document.getElementById("runs");
  const done = runs.filter((r) => r.status === "completed");
  const pick = { base: done[1]?.id, candidate: done[0]?.id };
  put(box, `
    <section class="sheet" aria-labelledby="r-title">
      <div class="sheet-head">
        <div>
          <h2 class="sheet-title" id="r-title">Runs</h2>
          <p class="sheet-note">Pick a base (B) and a candidate (C), then gate the release.</p>
        </div>
        <button class="btn" type="button" id="cmp-go" ${done.length >= 2 ? "" : 'disabled title="Needs two completed runs"'}>Gate release</button>
      </div>
      ${runs.length ? `
      <table class="ledger">
        <thead><tr><th scope="col">B / C</th><th scope="col">Run</th><th scope="col">Ver.</th><th scope="col">Status</th><th scope="col">Pass rate</th><th scope="col">Model</th><th scope="col">Started</th></tr></thead>
        <tbody>${runs.map((r) => {
          const ok = r.status === "completed";
          return `<tr class="run-row">
            <td><span class="pick">
              <label title="Base"><input type="radio" name="base" value="${r.id}" ${ok ? "" : "disabled"} ${pick.base === r.id ? "checked" : ""} aria-label="Use run ${r.id} as base"><span>B</span></label>
              <label title="Candidate"><input type="radio" name="cand" value="${r.id}" ${ok ? "" : "disabled"} ${pick.candidate === r.id ? "checked" : ""} aria-label="Use run ${r.id} as candidate"><span>C</span></label>
            </span></td>
            <td><a class="p-name" href="#/r/${r.id}">#${r.id}</a>${r.provider === "rescore" ? ' <span class="kv">re-scored</span>' : ""}</td>
            <td><span class="v">V${r.version}</span></td>
            <td data-label="Status">${status(r.status)}</td>
            <td style="min-width:160px" data-label="Pass rate">${ok ? meter(r.pass_rate) : '<span class="muted">—</span>'}</td>
            <td data-label="Model"><code>${esc(r.model)}</code></td>
            <td data-label="Started">${when(r.created_at)}</td>
          </tr>`;
        }).join("")}</tbody>
      </table>` : `
      <div class="empty"><strong>Nothing has gone through the dock</strong><p>Run a version above. A run takes a moment; this list updates by itself.</p></div>`}
    </section>`);

  box.querySelector("#cmp-go").onclick = () => {
    const b = box.querySelector("input[name=base]:checked")?.value;
    const c = box.querySelector("input[name=cand]:checked")?.value;
    if (!b || !c) { toast("Pick a base run (B) and a candidate run (C).", true); return; }
    if (b === c) { toast("Base and candidate must be different runs.", true); return; }
    location.hash = `#/c/${b}/${c}`;
  };

  if (runs.some((r) => r.status === "pending" || r.status === "running")) {
    pollTimer = setTimeout(async () => {
      try {
        const fresh = await api(`/runs?prompt_id=${prompt.id}`);
        if (token === renderToken) renderRuns(token, prompt, fresh);
      } catch { /* the next navigation retries */ }
    }, 1200);
  }
}

function renderCases(prompt, cases, latest, checks) {
  const box = document.getElementById("cases");
  const vars = latest?.variables || [];
  const types = Object.keys(checks);
  put(box, `
    <section class="sheet" aria-labelledby="c-title">
      <div class="sheet-head">
        <div>
          <h2 class="sheet-title" id="c-title">Test cases</h2>
          <p class="sheet-note">Every version runs against the same cases. Archived cases stay visible in old runs.</p>
        </div>
        <button class="btn ghost" type="button" id="case-toggle" aria-expanded="false" aria-controls="case-new">${icon.plus}Add test case</button>
      </div>
      <div class="drawer-body" id="case-new" hidden>
        <form class="form" id="case-form" novalidate>
          <label class="f"><span>Case name</span><input type="text" name="name" required maxlength="200" placeholder="mentions refund policy" autocomplete="off"></label>
          ${vars.length ? `<div class="form-row">${vars.map((v) => `
            <label class="f"><span>Input · {${esc(v)}}</span><input type="text" name="in:${esc(v)}" placeholder="Value for {${esc(v)}}"></label>`).join("")}</div>`
            : '<p class="hint">The latest template has no {variables}, so this case has no inputs.</p>'}
          <fieldset class="form" style="border:0;padding:0;margin:0">
            <legend class="hint" style="margin-bottom:8px">Checks · all must pass</legend>
            <div class="check-rows" id="check-rows"></div>
            <div><button class="btn sm quiet" type="button" id="check-add">${icon.plus}Another check</button></div>
          </fieldset>
          <div class="form-actions"><button class="btn" type="submit">Add test case</button><button class="btn quiet" type="button" id="case-cancel">Cancel</button></div>
        </form>
      </div>
      ${cases.length ? `
      <table class="ledger stacked">
        <thead><tr><th scope="col">Case</th><th scope="col">Inputs</th><th scope="col">Checks</th><th scope="col">Actions</th></tr></thead>
        <tbody>${cases.map((c) => `
          <tr>
            <td><b>${esc(c.name)}</b></td>
            <td data-label="Inputs">${Object.entries(c.inputs).map(([k, v]) => `<span class="kv">${esc(k)}=${esc(v)}</span>`).join("") || '<span class="muted">none</span>'}</td>
            <td data-label="Checks">${c.checks.map((k) => `<span class="chk"><b>${esc(k.type)}</b>${k.arg !== undefined && k.arg !== null ? `<code>${esc(Array.isArray(k.arg) ? k.arg.join(", ") : k.arg)}</code>` : ""}</span>`).join("")}</td>
            <td class="actions"><button class="btn sm quiet" type="button" data-archive="${c.id}" data-name="${esc(c.name)}">${icon.box}Archive</button></td>
          </tr>`).join("")}
        </tbody>
      </table>` : `
      <div class="empty"><strong>No test cases</strong><p>A run needs at least one case: inputs for the template, and checks the output must pass.</p></div>`}
    </section>`);

  const form = box.querySelector("#case-form");
  const rows = box.querySelector("#check-rows");
  drawer(box, "#case-toggle", "#case-new", "#case-cancel", form.name);

  const addCheckRow = () => {
    const row = document.createElement("div");
    row.className = "check-row";
    put(row, `
      <select aria-label="Check type">${types.map((t) => `<option value="${esc(t)}">${esc(t)}</option>`).join("")}</select>
      <input type="text" aria-label="Check argument">
      <button class="btn sm quiet" type="button">Remove</button>`);
    const sel = row.querySelector("select");
    const arg = row.querySelector("input");
    const sync = () => {
      const kind = checks[sel.value];
      arg.disabled = kind === null;
      arg.placeholder = kind === null ? "no argument" : kind === "int" ? "a number, e.g. 600"
        : kind === "list" ? "comma-separated keys" : sel.value === "regex" ? "a regular expression" : "text";
      arg.inputMode = kind === "int" ? "numeric" : "text";
      if (kind === null) arg.value = "";
    };
    sel.onchange = sync;
    sync();
    row.querySelector("button").onclick = () => { if (rows.children.length > 1) row.remove(); };
    rows.append(row);
    return sel;
  };
  addCheckRow();
  box.querySelector("#check-add").onclick = () => addCheckRow().focus();

  form.onsubmit = async (ev) => {
    ev.preventDefault();
    const name = form.name.value.trim();
    if (!name) { formError(form, "Give the case a name."); form.name.focus(); return; }
    const inputs = {};
    vars.forEach((v) => { inputs[v] = form.elements[`in:${v}`].value; });
    const list = [];
    for (const row of rows.children) {
      const type = row.querySelector("select").value;
      const raw = row.querySelector("input").value.trim();
      const kind = checks[type];
      if (kind === null) { list.push({ type }); continue; }
      if (!raw) { formError(form, `The ${type} check needs an argument.`); return; }
      list.push({ type, arg: kind === "int" ? Number(raw) : kind === "list" ? raw.split(",").map((s) => s.trim()).filter(Boolean) : raw });
    }
    const btn = form.querySelector("[type=submit]");
    busy(btn, true);
    try {
      await api(`/prompts/${prompt.id}/test-cases`, { method: "POST", body: { name, inputs, checks: list } });
      toast(`Test case ${name} added`);
      route();
    } catch (e) { formError(form, e.message); } finally { busy(btn, false); }
  };

  // archiving takes two clicks: the first arms the button for four seconds
  box.querySelectorAll("[data-archive]").forEach((b) => { b.onclick = async () => {
    if (b.dataset.armed !== "1") {
      b.dataset.armed = "1";
      b.textContent = "Confirm archive";
      b.classList.remove("quiet");
      setTimeout(() => {
        if (!b.isConnected) return;
        b.dataset.armed = "";
        put(b, `${icon.box}Archive`);
        b.classList.add("quiet");
      }, 4000);
      return;
    }
    busy(b, true);
    try {
      await api(`/test-cases/${b.dataset.archive}`, { method: "DELETE" });
      toast(`Archived ${b.dataset.name}`);
      route();
    } catch (e) { toast(e.message, true); busy(b, false); }
  }; });
}

// ---------- one run ----------

async function viewRun(token, id) {
  loading();
  const run = await api(`/runs/${id}`);
  const [prompt, siblings] = await Promise.all([api(`/prompts/${run.prompt_id}`), api(`/runs?prompt_id=${run.prompt_id}`)]);
  if (token !== renderToken) return;
  const others = siblings.filter((r) => r.status === "completed" && r.id !== run.id);
  const live = run.status === "pending" || run.status === "running";
  const notPassed = run.results.filter((r) => r.status === "fail" || r.status === "error");

  put(app, `
    ${crumbs([{ label: "Manifest", href: "#/" }, { label: prompt.name, href: `#/p/${prompt.id}` }, { label: `Run #${run.id}` }])}
    <section class="sheet" aria-labelledby="run-title">
      <div class="parcel">
        <div class="parcel-main">
          <h1 class="parcel-name" id="run-title">Run #${run.id}</h1>
          <p class="parcel-desc">${esc(prompt.name)} · version ${run.version} · ${plural(run.total, "case")}${run.provider === "rescore" ? " · re-scored from stored outputs, no LLM call" : ""}</p>
          ${run.error ? `<p class="err" style="margin-top:12px"><b>Run failed.</b> ${esc(run.error)}</p>` : ""}
        </div>
        <div class="parcel-code">
          <span class="route">V${run.version}</span>
          ${barcode(`PC-${pad(run.prompt_id)}-R${run.id}`)}
        </div>
      </div>
      <dl class="fields">
        <div class="field"><dt>Status</dt><dd>${status(run.status)}</dd></div>
        <div class="field"><dt>Pass rate</dt><dd>${run.status === "completed" ? meter(run.pass_rate) : "—"}</dd></div>
        <div class="field"><dt>Pass / fail / error</dt><dd>${run.passed} / ${run.failed} / ${run.errored}</dd></div>
        <div class="field"><dt>Model</dt><dd><code>${esc(run.model)}</code></dd></div>
        <div class="field"><dt>Provider</dt><dd>${esc(run.provider)}</dd></div>
        <div class="field"><dt>Finished</dt><dd>${when(run.finished_at)}</dd></div>
      </dl>
      ${run.status === "completed" ? `
      <div class="sheet-foot">
        <div class="form-actions">
          <button class="btn ghost" type="button" id="rescore" title="Apply the prompt's current checks to these stored outputs">${icon.redo}Re-score with current checks</button>
          ${others.length ? `
          <label class="f" style="margin-left:auto"><span>Gate against</span>
            <select id="cmp-with">${others.map((o) => `<option value="${o.id}">#${o.id} · v${o.version} · ${pct(o.pass_rate)}</option>`).join("")}</select></label>
          <button class="btn" type="button" id="cmp-run" style="align-self:end">Gate release</button>` : ""}
        </div>
      </div>` : ""}
    </section>
    <section class="sheet" aria-labelledby="res-title">
      <div class="sheet-head">
        <div>
          <h2 class="sheet-title" id="res-title">Results</h2>
          <p class="sheet-note">${live ? "Running. Results fill in as each case finishes."
            : notPassed.length ? `${plural(notPassed.length, "case")} did not pass; ${notPassed.length === 1 ? "it is" : "they are"} open below.`
            : run.results.length ? "Every case passed." : "No results."}</p>
        </div>
      </div>
      <div class="results">${run.results.map(resultRow).join("")}</div>
    </section>`);

  const rescore = document.getElementById("rescore");
  if (rescore) rescore.onclick = async () => {
    busy(rescore, true);
    try {
      const fresh = await api(`/runs/${run.id}/rescore`, { method: "POST" });
      toast(`Re-scored as run #${fresh.id}`);
      location.hash = `#/c/${run.id}/${fresh.id}`;
    } catch (e) { toast(e.message, true); busy(rescore, false); }
  };
  const cmp = document.getElementById("cmp-run");
  if (cmp) cmp.onclick = () => {
    const other = Number(document.getElementById("cmp-with").value);
    // the older run is the base, the newer one the candidate
    location.hash = other < run.id ? `#/c/${other}/${run.id}` : `#/c/${run.id}/${other}`;
  };

  if (live) pollTimer = setTimeout(() => { if (token === renderToken) route(); }, 1000);
}

function resultRow(r) {
  const failed = (r.check_details || []).filter((c) => !c.passed);
  const why = r.status === "error" ? r.error : failed.map((c) => c.detail).join(" · ");
  const open = r.status === "fail" || r.status === "error";
  return `
    <details class="result${open ? " is-fail" : ""}" ${open ? "open" : ""}>
      <summary>
        ${status(r.status)}
        <span><span class="r-name">${esc(r.test_case_name)}</span>${why ? `<span class="r-why">${esc(why)}</span>` : ""}</span>
        <span class="r-meta">${r.latency_ms !== null ? `${r.latency_ms} ms` : "—"} · ${r.tokens_in !== null ? `${r.tokens_in + r.tokens_out} tok` : "—"}</span>
      </summary>
      <div class="r-body">
        <div>
          <h3 class="cap" style="margin:0 0 6px">Checks</h3>
          <ul class="checklist">${(r.check_details || []).length
            ? r.check_details.map((c) => `<li>${status(c.passed ? "pass" : "fail")}<span><b>${esc(c.type)}</b> <span class="d">${esc(c.detail)}</span></span></li>`).join("")
            : r.checks.map((c) => `<li>${status("none")}<span><b>${esc(c.type)}</b> <span class="d">not scored</span></span></li>`).join("")}</ul>
        </div>
        <div>
          <h3 class="cap" style="margin:0 0 6px">Inputs</h3>
          ${Object.entries(r.inputs).map(([k, v]) => `<span class="kv">${esc(k)}=${esc(v)}</span>`).join("") || '<span class="muted">none</span>'}
        </div>
        ${r.rendered_prompt !== null ? `<div class="wide"><h3 class="cap" style="margin:0 0 6px">Rendered prompt</h3><pre class="tpl">${esc(r.rendered_prompt)}</pre></div>` : ""}
        ${r.output !== null ? `<div class="wide"><h3 class="cap" style="margin:0 0 6px">Output</h3><pre class="tpl">${esc(r.output)}</pre></div>` : ""}
        ${r.error ? `<div class="wide"><h3 class="cap" style="margin:0 0 6px">Error</h3><p class="err">${esc(r.error)}</p></div>` : ""}
      </div>
    </details>`;
}

// ---------- compare two runs: the gate ----------

async function viewCompare(token, base, candidate) {
  loading("Weighing the parcel");
  const baseRun = await api(`/runs/${base}`);
  const prompt = await api(`/prompts/${baseRun.prompt_id}`);
  const trail = (last) => crumbs([{ label: "Manifest", href: "#/" }, { label: prompt.name, href: `#/p/${prompt.id}` }, { label: last }]);
  let cmp;
  try {
    cmp = await api(`/runs/compare?base=${encodeURIComponent(base)}&candidate=${encodeURIComponent(candidate)}`);
  } catch (e) {
    if (token !== renderToken) return;
    put(app, `${trail("Gate")}
      <div class="sheet"><div class="empty"><strong>These runs can't be gated</strong><p class="err">${esc(e.message)}</p><a class="btn ghost" href="#/p/${prompt.id}">Back to ${esc(prompt.name)}</a></div></div>`);
    return;
  }
  if (token !== renderToken) return;

  const hold = cmp.verdict === "block";
  const s = cmp.summary;
  const m = cmp.metrics;
  const reasons = [];
  if (s.regressed) reasons.push(`<b>${plural(s.regressed, "case")} regressed</b>`);
  if (m.pass_rate.change < 0) reasons.push(`<b>the pass rate dropped ${pct(-m.pass_rate.change)}</b>`);
  const why = hold
    ? `Hold the release: ${reasons.join(" and ")}.`
    : `Clear to ship: <b>no regressions</b> and the pass rate did not drop${s.fixed ? `, with <b>${s.fixed} fixed</b>` : ""}.`;

  const fmt = (v, unit) => (v === null || v === undefined ? "—" : unit === "%" ? pct(v) : `${Math.round(v * 10) / 10}${unit}`);
  const metric = (label, d, unit, lowerIsBetter) => {
    let cls = "";
    let txt = "±0";
    if (d.change !== null && d.change !== 0) {
      if (lowerIsBetter !== null) cls = (lowerIsBetter ? d.change > 0 : d.change < 0) ? "bad" : "good";
      txt = `${d.change > 0 ? "+" : "−"}${fmt(Math.abs(d.change), unit)}`;
    }
    return `<tr><th scope="row">${label}</th><td class="base">${fmt(d.base, unit)}</td><td>${fmt(d.candidate, unit)}</td><td><span class="delta ${cls}">${txt}</span></td></tr>`;
  };

  const groups = [
    ["regressed", "Regressed", "Passed in the base run, not in the candidate."],
    ["fixed", "Fixed", "Failed before, passes now."],
    ["new", "New", "Only in the candidate run."],
    ["removed", "Removed", "Only in the base run."],
    ["still_failing", "Still failing", ""],
    ["still_passing", "Still passing", ""],
  ];

  put(app, `
    ${trail(`Gate #${cmp.base_run_id} → #${cmp.candidate_run_id}`)}
    <section class="sheet" aria-labelledby="g-title">
      <div class="verdict land">
        <div class="verdict-stamp">
          <h1 class="verdict-route" id="g-title">
            <span>V${cmp.base_version}</span><span class="arrow">${icon.arrow}<span class="sr">to</span></span><span>V${cmp.candidate_version}</span>
            <small>run #${cmp.base_run_id} → #${cmp.candidate_run_id}</small>
          </h1>
          <div class="big-stamp land ${hold ? "hold" : "ship"}" role="img" aria-label="Verdict: ${hold ? "hold" : "ship"}">${hold ? "Hold" : "Ship"}</div>
          <p class="verdict-why">${why}</p>
          <span class="verdict-api">verdict: "${esc(cmp.verdict)}"</span>
        </div>
        <div class="metrics">
          <table class="mledger">
            <thead><tr><th scope="col">Measure</th><th scope="col">Base #${cmp.base_run_id}</th><th scope="col">Cand. #${cmp.candidate_run_id}</th><th scope="col">Δ</th></tr></thead>
            <tbody>
              ${metric("Pass rate", m.pass_rate, "%", false)}
              ${metric("Avg latency", m.avg_latency_ms, " ms", true)}
              ${metric("p95 latency", m.p95_latency_ms, " ms", true)}
              ${metric("Tokens", m.total_tokens, "", null)}
            </tbody>
          </table>
        </div>
      </div>
      <nav class="tally" aria-label="Cases by outcome">
        ${groups.map(([k, label]) => s[k]
          ? `<a href="#g-${k}" data-jump="g-${k}" class="has${k === "regressed" ? " is-hold" : k === "fixed" ? " is-ship" : ""}"><b>${s[k]}</b> ${label.toLowerCase()}</a>`
          : `<a href="#g-${k}" aria-disabled="true" tabindex="-1">0 ${label.toLowerCase()}</a>`).join("")}
      </nav>
      ${groups.filter(([k]) => cmp.cases[k].length).map(([k, label, note]) => `
        <section class="group${k === "regressed" ? " is-hold" : ""}" id="g-${k}" aria-labelledby="gh-${k}">
          <h2 class="group-h" id="gh-${k}">${label} <span class="count">${cmp.cases[k].length}</span></h2>
          ${note ? `<p class="hint" style="padding:0 20px 8px">${note}</p>` : ""}
          <table class="cmp">
            <thead><tr><th scope="col">Case</th><th scope="col">Base #${cmp.base_run_id}</th><th scope="col">Candidate #${cmp.candidate_run_id}</th><th scope="col">Why</th></tr></thead>
            <tbody>${cmp.cases[k].map((c) => `
              <tr>
                <td><b>${esc(c.test_case_name)}</b></td>
                <td data-label="Base #${cmp.base_run_id}">${c.base_status ? status(c.base_status) : '<span class="muted">—</span>'}</td>
                <td data-label="Candidate #${cmp.candidate_run_id}">${c.candidate_status ? status(c.candidate_status) : '<span class="muted">—</span>'}</td>
                <td class="why">${esc(c.candidate_error || c.candidate_failed_checks.join(" · ")) || '<span class="muted">—</span>'}</td>
              </tr>`).join("")}
            </tbody>
          </table>
        </section>`).join("")}
      <div class="sheet-foot form-actions">
        <a class="btn ghost" href="#/c/${esc(candidate)}/${esc(base)}">${icon.swap}Swap base and candidate</a>
        <a class="btn quiet" href="#/r/${cmp.candidate_run_id}">Open candidate run</a>
        <a class="btn quiet" href="#/r/${cmp.base_run_id}">Open base run</a>
      </div>
    </section>`);

  app.querySelectorAll("[data-jump]").forEach((a) => { a.onclick = (ev) => {
    ev.preventDefault();
    document.getElementById(a.dataset.jump)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }; });
}
