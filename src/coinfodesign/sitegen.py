"""Static PT-BR site generator: a single reactive scenario laboratory.

One shared control set (n, tau, five sensor probabilities) drives the
overview chart, the selected-scenario analysis, and the 40-row table
simultaneously. The Python build only emits the per-(n,tau) canonical
data (never precomputed R values); all probability-dependent numbers
are (re)computed client-side from that canonical data, in JS, using the
same division-free formula as coinfodesign.polynomial.reliability.
"""
from __future__ import annotations

import math
from decimal import Decimal
from pathlib import Path

from . import render
from .cases import TAUS

NS = tuple(2 ** k for k in range(1, 11))
TAU_COLORS = {"0.02": "#6a7bff", "0.05": "#2fb3a3", "0.10": "#e2a33a", "0.20": "#d6556b"}


def _boolean_condition(minimal_sets: list[list[int]]) -> str:
    if not minimal_sets:
        return "falso"
    parts = []
    for group in minimal_sets:
        if len(group) == 1:
            parts.append(f"S{group[0]}")
        else:
            parts.append("(" + " &and; ".join(f"S{i}" for i in group) + ")")
    return " &or; ".join(parts)


def _chart_svg(cases_by_key: dict, selected: tuple[int, str], width: int = 640, height: int = 320) -> str:
    """Initial server-rendered chart at the default scenario (p=90% all).
    JS rebuilds this exact markup on load and on every control change."""
    pad_l, pad_r, pad_t, pad_b = 48, 16, 16, 32
    plot_w, plot_h = width - pad_l - pad_r, height - pad_t - pad_b

    def x_of(n: int) -> float:
        lo, hi = math.log2(NS[0]), math.log2(NS[-1])
        return pad_l + (math.log2(n) - lo) / (hi - lo) * plot_w

    def y_of(r: Decimal) -> float:
        return pad_t + (1 - float(r)) * plot_h

    sel_n, sel_tau = selected
    paths, points_markup = [], []
    for tau_str, color in TAU_COLORS.items():
        coords = []
        for n in NS:
            case = cases_by_key[f"n{n}-tau{tau_str}"]
            coords.append((n, x_of(n), y_of(Decimal(case["r_at_90"]))))
        d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for _, x, y in coords)
        paths.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="2"/>')
        for n, x, y in coords:
            if n == sel_n and tau_str == sel_tau:
                points_markup.append(
                    f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5.5" fill="{color}" '
                    f'stroke="var(--fg)" stroke-width="2"/>'
                )
            else:
                points_markup.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.5" fill="{color}"/>')

    gridlines = []
    for n in NS:
        x = x_of(n)
        gridlines.append(
            f'<line x1="{x:.1f}" y1="{pad_t}" x2="{x:.1f}" y2="{pad_t+plot_h}" stroke="currentColor" stroke-opacity="0.08"/>'
        )
        gridlines.append(
            f'<text x="{x:.1f}" y="{pad_t+plot_h+16}" font-size="9" text-anchor="middle" fill="currentColor">{n}</text>'
        )
    for frac in (0, 0.25, 0.5, 0.75, 1.0):
        y = pad_t + (1 - frac) * plot_h
        gridlines.append(
            f'<line x1="{pad_l}" y1="{y:.1f}" x2="{pad_l+plot_w}" y2="{y:.1f}" stroke="currentColor" stroke-opacity="0.08"/>'
        )
        gridlines.append(
            f'<text x="{pad_l-6}" y="{y+3:.1f}" font-size="9" text-anchor="end" fill="currentColor">{frac:.2f}</text>'
        )

    legend = "".join(
        f'<span class="legend-item"><i style="background:{color}"></i>&tau;={tau}</span>'
        for tau, color in TAU_COLORS.items()
    )
    svg = (
        f'<svg viewBox="0 0 {width} {height}" role="img" id="chart-svg" '
        f'aria-label="Confiabilidade por n, quatro séries de tau, ponto destacado no cenário selecionado">'
        + "".join(gridlines) + "".join(paths) + "".join(points_markup) + "</svg>"
    )
    return f'{svg}<div class="legend">{legend}</div>'


def _panorama_table(payload: dict, selected: tuple[int, str]) -> str:
    sel_n, sel_tau = selected
    rows = []
    for case in payload["cases"]:
        key = case["case_key"]
        is_selected = case["n_per_class"] == sel_n and case["tau"] == sel_tau
        cls = ' class="selected"' if is_selected else ""
        counts_str = ", ".join(f"a{k}={v}" for k, v in enumerate(case["counts"]))
        rows.append(
            f'<tr id="row-{key}" data-n="{case["n_per_class"]}" data-tau="{case["tau"]}" '
            f'tabindex="0" role="button"{cls}>'
            f"<td>{case['n_per_class']}</td><td>{case['tau']}</td>"
            f"<td>{_boolean_condition(case['minimal_sets'])}</td>"
            f"<td>{case['states']}</td>"
            f"<td class=\"mono\">{counts_str}</td>"
            f"<td class=\"mono\">{case['h_univariate_html']}</td>"
            f"<td class=\"mono\" id=\"r-cell-{key}\">{case['r_at_90_br']}</td>"
            f"<td><details><summary>H estruturado e expandido (x&#8321;..x&#8325;)</summary>"
            f"<p class=\"mono\"><strong>Estruturado:</strong> {case['h_structured_html']}</p>"
            f"<p class=\"mono\"><strong>Expandido:</strong> {case['h_expanded_html']}</p>"
            f"</details></td>"
            f"</tr>"
        )
    return (
        '<table class="panorama" id="panorama-table">'
        "<caption>40 casos (10 tamanhos de amostra &times; 4 cortes de tau). Clique ou pressione Enter numa linha "
        "para torná-la o cenário selecionado acima. A coluna R usa os controles de probabilidade atuais.</caption>"
        "<thead><tr><th>n</th><th>&tau;</th><th>Condição booleana</th><th>Estados</th>"
        "<th>a&#8320;&#8230;a&#8325;</th><th>H(x)</th><th>R (controles atuais)</th><th>Formas completas</th></tr></thead>"
        "<tbody>" + "".join(rows) + "</tbody></table>"
    )


def _plateau_table(payload: dict) -> str:
    rows = []
    for tau in TAUS:
        n = payload["plateau_start_n"][f"{tau:.2f}"]
        rows.append(f"<tr><td>{tau:.2f}</td><td>{n}</td></tr>")
    return (
        '<table class="plateau"><caption>Início do sufixo terminal idêntico por &tau; '
        "(igualdade exata do polinômio canônico / antecadeia mínima, nesta grade finita de n)."
        "</caption><thead><tr><th>&tau;</th><th>n inicial</th></tr></thead>"
        "<tbody>" + "".join(rows) + "</tbody></table>"
    )


CSS = """
:root {
  --bg: #0b0d12; --fg: #e8ebf2; --muted: #9aa3b5; --accent: #6a7bff;
  --card: #141822; --border: #232938; --selected: #22304a;
}
@media (prefers-color-scheme: light) {
  :root { --bg: #fafbfe; --fg: #161a22; --muted: #5b6475; --accent: #3b4ccb;
    --card: #ffffff; --border: #e2e6ef; --selected: #eef3ff; }
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--fg);
  font: 16px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif;
}
header, main, footer { max-width: 980px; margin: 0 auto; padding: 1rem 1.25rem; }
header { border-bottom: 1px solid var(--border); }
h1 { font-size: 1.4rem; margin: 0.2rem 0; }
.subtitle { color: var(--muted); font-size: 0.95rem; }
nav a { color: var(--accent); margin-right: 1rem; text-decoration: none; font-weight: 600; }
section { margin: 2rem 0; }
h2 { border-left: 4px solid var(--accent); padding-left: 0.6rem; }
.table-scroll { overflow-x: auto; border: 1px solid var(--border); border-radius: 8px; }
table { border-collapse: collapse; width: 100%; font-size: 0.88rem; }
table.plateau { width: auto; }
caption { text-align: left; color: var(--muted); padding: 0.5rem; font-size: 0.82rem; }
th, td { padding: 0.45rem 0.6rem; border-bottom: 1px solid var(--border); text-align: left; vertical-align: top; }
tr[data-n] { cursor: pointer; }
tr[data-n]:hover { background: color-mix(in srgb, var(--selected) 55%, transparent); }
tr[data-n]:focus-visible { outline: 2px solid var(--accent); outline-offset: -2px; }
tr.selected { background: var(--selected); }
.mono { font-family: "JetBrains Mono", Menlo, Consolas, monospace; }
details > summary { cursor: pointer; color: var(--accent); }
.chart svg { width: 100%; max-width: 640px; height: auto; color: var(--fg); }
.legend { display: flex; gap: 1rem; flex-wrap: wrap; font-size: 0.8rem; margin-top: 0.4rem; }
.legend-item i { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 0.3rem; }
.controls-grid { display: grid; gap: 1rem; grid-template-columns: 1fr; }
@media (min-width: 720px) { .controls-grid { grid-template-columns: 320px 1fr; } }
.controls-grid > .card { min-width: 0; }
.card { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 1rem; min-width: 0; }
.selectors { display: flex; gap: 0.75rem; flex-wrap: wrap; margin-bottom: 0.75rem; }
.selectors label { display: flex; flex-direction: column; font-size: 0.8rem; gap: 0.25rem; }
select, button { font: inherit; padding: 0.35rem 0.5rem; border-radius: 6px; border: 1px solid var(--border);
  background: var(--card); color: var(--fg); }
button { cursor: pointer; }
.slider-row { display: flex; align-items: center; gap: 0.6rem; margin: 0.5rem 0; }
.slider-row label { width: 150px; font-size: 0.85rem; flex-shrink: 0; }
.slider-row input[type=range] { flex: 1; }
.slider-row output { width: 3.2rem; text-align: right; font-family: monospace; }
.presets { display: flex; gap: 0.5rem; margin: 0.75rem 0; flex-wrap: wrap; }
.formula-block { margin: 0.6rem 0; overflow-x: auto; white-space: nowrap; padding-bottom: 0.2rem; }
.formula-block .label { color: var(--muted); font-size: 0.78rem; display: block; margin-bottom: 0.15rem; white-space: normal; }
.r-output { font-size: 1.6rem; font-weight: 700; color: var(--accent); }
.error-banner { background: #5a1f1f; color: #ffe3e3; padding: 0.6rem 1rem; border-radius: 8px; display: none; margin-bottom: 1rem; }
footer { border-top: 1px solid var(--border); color: var(--muted); font-size: 0.8rem; }
footer a { color: var(--accent); }
sup, sub { line-height: 0; }
code { overflow-wrap: anywhere; word-break: break-all; }
"""


def _js(build_commit: str) -> str:
    return r"""
function tally(indices, labelOf) {
  const order = [], counts = {};
  [...indices].sort((a,b)=>a-b).forEach(i => {
    const lbl = labelOf[i];
    if (!(lbl in counts)) { counts[lbl] = 0; order.push(lbl); }
    counts[lbl] += 1;
  });
  return order.map(lbl => [lbl, counts[lbl]]);
}
function monoStr(indices, labelOf) {
  if (!indices.length) return "1";
  return tally(indices, labelOf).map(([lbl,c]) => c===1 ? lbl : `${lbl}<sup>${c}</sup>`).join("");
}
function freeProdStr(indices, labelOf) {
  if (!indices.length) return "1";
  return tally(indices, labelOf).map(([lbl,c]) => c===1 ? `(1+${lbl})` : `(1+${lbl})<sup>${c}</sup>`).join("");
}
function renderStructured(node, labelOf) {
  switch (node.type) {
    case "const": return [String(node.value), false];
    case "var": return [labelOf[node.i], false];
    case "mono": return [monoStr(node.indices, labelOf), false];
    case "freeprod": return [freeProdStr(node.indices, labelOf), false];
    case "altprod": return [`[${freeProdStr(node.indices, labelOf)}&minus;1]`, false];
    case "add": {
      const parts = node.terms.map(t => { const [txt,isSum]=renderStructured(t,labelOf); return isSum?`(${txt})`:txt; });
      return [parts.join(" + "), true];
    }
    case "mul": {
      const parts = node.factors.map(f => { const [txt,isSum]=renderStructured(f,labelOf); return isSum?`(${txt})`:txt; });
      return [parts.join(""), false];
    }
  }
  throw new Error("unknown node " + node.type);
}
function renderExpanded(canonicalPairs, labelOf) {
  if (!canonicalPairs.length) return "0";
  const ordered = [...canonicalPairs].sort((a,b)=> a[0].length-b[0].length || (a[0].join(",")<b[0].join(",")?-1:1));
  return ordered.map(([subset,coeff]) => { const m = monoStr(subset, labelOf); return coeff===1? m : `${coeff}${m}`; }).join(" + ");
}
function labelFor(group) {
  if (group.length === 5) return "x";
  if (group.length === 1) return `x<sub>${group[0]}</sub>`;
  return `x<sub>${[...group].sort((a,b)=>a-b).join("")}</sub>`;
}
function groupsFromValues(percents) {
  const byValue = {};
  for (let i=1;i<=5;i++) { (byValue[percents[i]] ||= []).push(i); }
  return Object.values(byValue).sort((a,b)=>Math.min(...a)-Math.min(...b));
}
function labelsFromGroups(groups) {
  const labels = {};
  groups.forEach(g => { const lbl = labelFor(g); g.forEach(i => labels[i]=lbl); });
  return labels;
}
function groupSignature(subset, groups) { return groups.map(g => subset.filter(i=>g.includes(i)).length); }
function groupedCanonical(canonicalPairs, groups) {
  const result = new Map();
  for (const [subset, coeff] of canonicalPairs) {
    const key = groupSignature(subset, groups).join(",");
    result.set(key, (result.get(key)||0) + coeff);
  }
  return [...result.entries()].map(([k,v]) => [k.split(",").map(Number), v]);
}
function renderGroupedExpanded(groupedPairs, groups) {
  if (!groupedPairs.length) return "0";
  const labels = groups.map(labelFor);
  const ordered = [...groupedPairs].sort((a,b)=> a[0].reduce((s,x)=>s+x,0)-b[0].reduce((s,x)=>s+x,0));
  return ordered.map(([exps,coeff]) => {
    const factors = [];
    exps.forEach((e,idx) => { if (e>0) factors.push(e===1?labels[idx]:`${labels[idx]}<sup>${e}</sup>`); });
    const m = factors.length? factors.join("") : "1";
    return coeff===1? m : `${coeff}${m}`;
  }).join(" + ");
}

// Division-free R numerator over a denominator of 100^5 = 1e10 (exact,
// well within JS's safe integer range), mirroring coinfodesign.polynomial.reliability.
function computeRNumerator(canonicalPairs, percents) {
  let total = 0;
  for (const [subset, coeff] of canonicalPairs) {
    let term = coeff;
    for (let i=1;i<=5;i++) { term *= subset.includes(i) ? percents[i] : (100 - percents[i]); }
    total += term;
  }
  return total;
}
function formatPercentBR(numeratorOver1e10) {
  const thousandths = Math.round(numeratorOver1e10 / 1e5); // percent * 1000
  const intPart = Math.floor(thousandths/1000);
  const fracDigits = String(thousandths % 1000).padStart(3,"0");
  return fracDigits === "000" ? `${intPart}%` : `${intPart},${fracDigits}%`;
}
function booleanCondition(minimalSets) {
  if (!minimalSets.length) return "falso";
  return minimalSets.map(g => g.length===1 ? `S${g[0]}` : "(" + g.map(i=>`S${i}`).join(" &and; ") + ")").join(" &or; ");
}

let DATA = null;
const state = { n: 512, tau: "0.10", percents: {1:90,2:90,3:90,4:90,5:90} };

function caseFor(n, tau) { return DATA.cases.find(c => c.n_per_class===n && c.tau===tau); }

const NS = [2,4,8,16,32,64,128,256,512,1024];
const TAU_COLORS = {"0.02":"#6a7bff","0.05":"#2fb3a3","0.10":"#e2a33a","0.20":"#d6556b"};

function renderChart() {
  const width = 640, height = 320;
  const padL = 48, padR = 16, padT = 16, padB = 32;
  const plotW = width - padL - padR, plotH = height - padT - padB;
  const lo = Math.log2(NS[0]), hi = Math.log2(NS[NS.length-1]);
  const xOf = n => padL + (Math.log2(n) - lo) / (hi - lo) * plotW;
  const yOf = r => padT + (1 - r) * plotH;

  const paths = [], points = [];
  for (const [tauStr, color] of Object.entries(TAU_COLORS)) {
    const coords = NS.map(n => {
      const c = caseFor(n, tauStr);
      const r = computeRNumerator(c.canonical, state.percents) / 1e10;
      return [n, xOf(n), yOf(r)];
    });
    const d = "M " + coords.map(([,x,y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" L ");
    paths.push(`<path d="${d}" fill="none" stroke="${color}" stroke-width="2"/>`);
    for (const [n,x,y] of coords) {
      if (n === state.n && tauStr === state.tau) {
        points.push(`<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="5.5" fill="${color}" stroke="var(--fg)" stroke-width="2"/>`);
      } else {
        points.push(`<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="2.5" fill="${color}"/>`);
      }
    }
  }
  const gridlines = [];
  for (const n of NS) {
    const x = xOf(n);
    gridlines.push(`<line x1="${x.toFixed(1)}" y1="${padT}" x2="${x.toFixed(1)}" y2="${padT+plotH}" stroke="currentColor" stroke-opacity="0.08"/>`);
    gridlines.push(`<text x="${x.toFixed(1)}" y="${padT+plotH+16}" font-size="9" text-anchor="middle" fill="currentColor">${n}</text>`);
  }
  for (const frac of [0,0.25,0.5,0.75,1.0]) {
    const y = padT + (1-frac)*plotH;
    gridlines.push(`<line x1="${padL}" y1="${y.toFixed(1)}" x2="${padL+plotW}" y2="${y.toFixed(1)}" stroke="currentColor" stroke-opacity="0.08"/>`);
    gridlines.push(`<text x="${padL-6}" y="${(y+3).toFixed(1)}" font-size="9" text-anchor="end" fill="currentColor">${frac.toFixed(2)}</text>`);
  }
  const legend = Object.entries(TAU_COLORS).map(([tau,color]) =>
    `<span class="legend-item"><i style="background:${color}"></i>&tau;=${tau}</span>`).join("");
  const label = `Confiabilidade por n, cenário destacado n=${state.n}, &tau;=${state.tau}, `
    + Object.entries(state.percents).map(([i,p]) => `p${i}=${p}%`).join(", ");
  const svg = `<svg viewBox="0 0 ${width} ${height}" role="img" id="chart-svg" aria-label="${label}">`
    + gridlines.join("") + paths.join("") + points.join("") + "</svg>";
  document.getElementById("chart-container").innerHTML = svg + `<div class="legend">${legend}</div>`;
}

function renderScenario() {
  const errorBanner = document.getElementById("lab-error");
  const current = caseFor(state.n, state.tau);
  if (!current) { errorBanner.style.display = "block"; errorBanner.textContent = "Erro: caso não encontrado nos dados carregados."; return; }
  errorBanner.style.display = "none";

  const identityLabels = {1:"x<sub>1</sub>",2:"x<sub>2</sub>",3:"x<sub>3</sub>",4:"x<sub>4</sub>",5:"x<sub>5</sub>"};
  const args = "(x<sub>1</sub>,x<sub>2</sub>,x<sub>3</sub>,x<sub>4</sub>,x<sub>5</sub>)";
  document.getElementById("lab-condition").innerHTML = booleanCondition(current.minimal_sets);
  const [structuredText] = renderStructured(current.tree, identityLabels);
  document.getElementById("lab-structured-canonical").innerHTML =
    `<span class="label">H<sub>${state.n},${state.tau}</sub>${args} (geral, estruturado) =</span> ${structuredText || "0"}`;
  document.getElementById("lab-expanded-canonical").innerHTML =
    `<span class="label">H<sub>${state.n},${state.tau}</sub>${args} (geral, expandido) =</span> ${renderExpanded(current.canonical, identityLabels)}`;

  const groups = groupsFromValues(state.percents);
  const groupLabels = labelsFromGroups(groups);
  const [groupedStructuredText] = renderStructured(current.tree, groupLabels);
  const groupedCanon = groupedCanonical(current.canonical, groups);
  const groupArgs = "(" + groups.map(labelFor).join(",") + ")";
  document.getElementById("lab-structured-grouped").innerHTML =
    `<span class="label">H<sup>grp</sup><sub>${state.n},${state.tau}</sub>${groupArgs} (especializado, estruturado) =</span> ${groupedStructuredText || "0"}`;
  document.getElementById("lab-expanded-grouped").innerHTML =
    `<span class="label">H<sup>grp</sup><sub>${state.n},${state.tau}</sub>${groupArgs} (especializado, expandido) =</span> ${renderGroupedExpanded(groupedCanon, groups)}`;
  document.getElementById("lab-univariate").innerHTML =
    `<span class="label">H<sub>${state.n},${state.tau}</sub>(x) (todas iguais) =</span> ${current.h_univariate_html}`;

  const allEqual = new Set(Object.values(state.percents)).size === 1;
  const rFormulaLabel = document.getElementById("lab-r-formula-label");
  if (allEqual) {
    rFormulaLabel.innerHTML = `R<sub>${state.n},${state.tau}</sub>(p) = &sum; a<sub>k</sub> p<sup>k</sup>(1&minus;p)<sup>5&minus;k</sup>, p=${state.percents[1]}%`;
  } else {
    rFormulaLabel.innerHTML = `R<sub>${state.n},${state.tau}</sub>(p<sub>1</sub>,...,p<sub>5</sub>) = &sum;<sub>A geral</sub> &prod;<sub>i&isin;A</sub>p<sub>i</sub> &prod;<sub>i&notin;A</sub>(1&minus;p<sub>i</sub>)`;
  }
  const numerator = computeRNumerator(current.canonical, state.percents);
  document.getElementById("lab-r-value").textContent = formatPercentBR(numerator);
}

function renderTable() {
  for (const c of DATA.cases) {
    const numerator = computeRNumerator(c.canonical, state.percents);
    const cell = document.getElementById(`r-cell-${c.case_key}`);
    if (cell) cell.textContent = formatPercentBR(numerator);
    const row = document.getElementById(`row-${c.case_key}`);
    if (row) {
      const isSelected = c.n_per_class === state.n && c.tau === state.tau;
      row.classList.toggle("selected", isSelected);
      row.setAttribute("aria-pressed", String(isSelected));
    }
  }
}

function renderAll() { renderChart(); renderScenario(); renderTable(); }

function selectScenario(n, tau) {
  state.n = n; state.tau = tau;
  document.getElementById("n-select").value = String(n);
  document.getElementById("tau-select").value = tau;
  renderAll();
}

function wireControls() {
  for (let i=1;i<=5;i++) {
    const input = document.getElementById(`p${i}`);
    const output = document.getElementById(`p${i}-out`);
    input.addEventListener("input", () => {
      state.percents[i] = Number(input.value);
      output.textContent = input.value + "%";
      renderAll();
    });
  }
  document.getElementById("preset-all90").addEventListener("click", () => {
    for (let i=1;i<=5;i++) { state.percents[i]=90; document.getElementById(`p${i}`).value=90; document.getElementById(`p${i}-out`).textContent="90%"; }
    renderAll();
  });
  document.getElementById("preset-mixed").addEventListener("click", () => {
    const mixed = {1:90,2:70,3:90,4:40,5:90};
    for (let i=1;i<=5;i++) { state.percents[i]=mixed[i]; document.getElementById(`p${i}`).value=mixed[i]; document.getElementById(`p${i}-out`).textContent=mixed[i]+"%"; }
    renderAll();
  });
  document.getElementById("n-select").addEventListener("change", (e) => { state.n = Number(e.target.value); renderAll(); });
  document.getElementById("tau-select").addEventListener("change", (e) => { state.tau = e.target.value; renderAll(); });

  const tbody = document.querySelector("#panorama-table tbody");
  tbody.addEventListener("click", (e) => {
    const row = e.target.closest("tr[data-n]");
    if (row) selectScenario(Number(row.dataset.n), row.dataset.tau);
  });
  tbody.addEventListener("keydown", (e) => {
    if (e.key !== "Enter" && e.key !== " ") return;
    const row = e.target.closest("tr[data-n]");
    if (row) { e.preventDefault(); selectScenario(Number(row.dataset.n), row.dataset.tau); }
  });
}

async function main() {
  const errorBanner = document.getElementById("lab-error");
  try {
    const res = await fetch("data/cases.json");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    DATA = await res.json();
  } catch (err) {
    errorBanner.style.display = "block";
    errorBanner.textContent = "Erro ao carregar os dados (data/cases.json). " + err.message;
    return;
  }
  wireControls();
  renderAll();
}
main();
""".strip() + "\n"


def generate(out_dir: Path, payload: dict, build_commit: str) -> None:
    assets = out_dir / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    (assets / "style.css").write_text(CSS.strip() + "\n", encoding="utf-8")
    (assets / "app.js").write_text(_js(build_commit), encoding="utf-8")

    cases_by_key = {c["case_key"]: c for c in payload["cases"]}
    selected = (512, "0.10")
    classroom = cases_by_key["n512-tau0.10"]

    n_options = "".join(
        f'<option value="{n}" {"selected" if n==512 else ""}>{n}</option>'
        for n in NS
    )
    tau_options = "".join(
        f'<option value="{t:.2f}" {"selected" if f"{t:.2f}"=="0.10" else ""}>{t:.2f}</option>'
        for t in TAUS
    )
    sliders = "".join(
        f'<div class="slider-row"><label for="p{i}">S{i} &middot; {name}</label>'
        f'<input type="range" id="p{i}" min="0" max="100" value="90">'
        f'<output id="p{i}-out" for="p{i}">90%</output></div>'
        for i, name in enumerate(
            ["PT08.S1(CO)", "PT08.S2(NMHC)", "PT08.S3(NOx)", "PT08.S4(NO2)", "PT08.S5(O3)"], start=1
        )
    )

    html = f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CoInfoDesign &middot; Confiabilidade por funções geradoras</title>
<link rel="stylesheet" href="assets/style.css">
</head>
<body>
<header>
<h1>CoInfoDesign</h1>
<p class="subtitle">Disponibilidade de preditores previamente avaliados via funções geradoras &middot;
ICP747, PPGI/UFRJ &middot; build <code>{build_commit}</code></p>
<nav><a href="#visao-geral">Visão geral</a><a href="#cenario">Cenário</a><a href="#tabela">Tabela</a></nav>
<p class="subtitle">40 casos (n &isin; {{2,4,...,1024}} &times; &tau; &isin; {{0,02; 0,05; 0,10; 0,20}}), calculados a
partir das perdas médias persistidas da simulação CoInfoSim <code>000018</code> (commit de origem
<code>{payload['source']['commit'][:12]}</code>). Nenhum treinamento, reamostragem ou Monte Carlo é executado aqui;
apenas a perda já publicada é lida e comparada ao corte &tau;. Um único conjunto de controles abaixo governa o
gráfico, a análise do cenário e a tabela, todos recalculados a partir dos dados de origem a cada alteração.</p>
</header>
<main>

<div id="lab-error" class="error-banner" role="alert"></div>

<section id="controles">
<div class="controls-grid">
<div class="card">
<h2>Controles</h2>
<div class="selectors">
<label>n por classe <select id="n-select">{n_options}</select></label>
<label>&tau; <select id="tau-select">{tau_options}</select></label>
</div>
{sliders}
<div class="presets">
<button id="preset-all90" type="button">Predefinição: todos 90%</button>
<button id="preset-mixed" type="button">Predefinição mista [90,70,90,40,90]</button>
</div>
</div>
<div class="card" id="cenario">
<h2>Cenário selecionado</h2>
<p><strong>Condição booleana:</strong> <span id="lab-condition"></span></p>
<div class="formula-block mono" id="lab-structured-canonical"></div>
<div class="formula-block mono" id="lab-expanded-canonical"></div>
<div class="formula-block mono" id="lab-structured-grouped"></div>
<div class="formula-block mono" id="lab-expanded-grouped"></div>
<div class="formula-block mono" id="lab-univariate"></div>
<div class="formula-block" id="lab-r-formula-label"></div>
<p class="r-output" id="lab-r-value">{classroom['r_at_90_br']}</p>
</div>
</div>
<p class="subtitle">Padrão inicial: n=512, &tau;=0,10, p<sub>1..5</sub>=90% &rarr; H(x)={classroom['h_univariate_html']},
R=<strong>{classroom['r_at_90_br']}</strong>. A função geradora geral (acima) permanece estruturalmente inalterada ao
mudar as probabilidades; apenas a especialização por grupos e o valor de R respondem aos controles.</p>
</section>

<section id="visao-geral">
<h2>Visão geral &middot; confiabilidade vs. n</h2>
<div class="chart" id="chart-container">{_chart_svg(cases_by_key, selected)}</div>
</section>

<section id="tabela">
<h2>Tabela dos 40 cenários</h2>
<div class="table-scroll">{_panorama_table(payload, selected)}</div>
{_plateau_table(payload)}
<p class="subtitle">Fonte: <a href="https://github.com/paulorenatoaz/coinfosim/tree/{payload['source']['commit']}">
paulorenatoaz/coinfosim@{payload['source']['commit'][:12]}</a>, execução {payload['source']['run']}. Ver
<a href="ATTRIBUTION.md">ATTRIBUTION.md</a> e <a href="data/cases.json">data/cases.json</a> para reprodução.</p>
</section>

</main>
<footer>
<p>CoInfoDesign &copy; Paulo Renato Azevedo &middot; código sob
<a href="LICENSE">GPL-3.0-or-later</a> &middot; dados de origem: CoInfoSim (GPL-3.0-or-later) e
UCI Air Quality (CC BY 4.0, uso de pesquisa) &mdash; ver <a href="ATTRIBUTION.md">ATTRIBUTION.md</a> e
<a href="CITATION.cff">CITATION.cff</a>. Build <code>{build_commit}</code>.</p>
</footer>
<script src="assets/app.js"></script>
</body>
</html>
"""
    (out_dir / "index.html").write_text(html, encoding="utf-8")
    (out_dir / "build_id.txt").write_text(build_commit + "\n", encoding="utf-8")
