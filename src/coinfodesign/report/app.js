"use strict";

const get = id => document.getElementById(id);
const nSelect = get("n-select");
const tauSelect = get("tau-select");
const sliders = [...document.querySelectorAll(".slider-row input")];
const nValues = [...nSelect.options].map(option => Number(option.value));
const taus = [...tauSelect.options].map(option => option.value);
const table = get("panorama-table");
const defaultPercents = sliders.map(input => Number(input.defaultValue));
const mixedPercents = [90, 70, 90, 40, 90];
const state = {
  n: Number(nSelect.value),
  tau: tauSelect.value,
  percents: defaultPercents,
};
const keyFor = (n, tau) => `n${n}-tau${tau}`;
const sensor = i => `S<sub>${i}</sub>`;
const atom = html => `<span class="atom">${html}</span>`;
const sum = terms => terms.map(atom).join(" + ");
const caseLabel = c => `n = ${c.n_per_class} · τ = ${c.tau.replace(".", ",")}`;
let cases;
let weights;

function structuredBreaks(html) {
  return html.replace(/(<\/sub>|<\/sup>|[)\]])(?=[x(\[])/g, "$1<wbr>");
}

function groupsFromValues(percents) {
  const byValue = new Map();
  percents.forEach((value, index) => {
    if (!byValue.has(value)) byValue.set(value, []);
    byValue.get(value).push(index + 1);
  });
  return [...byValue.values()];
}

function groupLabel(group) {
  return group.length === sliders.length ? "x" : `x<sub>${group.join("")}</sub>`;
}

function power(factor, exponent) {
  return exponent === 1 ? factor : `${factor}<sup>${exponent}</sup>`;
}

function product(indices, labels, factor) {
  const powers = new Map();
  for (const i of indices) {
    const label = labels[i];
    powers.set(label, (powers.get(label) || 0) + 1);
  }
  return [...powers].map(([label, exponent]) => power(factor(label), exponent)).join("") || "1";
}

function renderStructured(node, labels) {
  const parenthesize = child => {
    const html = renderStructured(child, labels);
    return child.type === "add" ? `(${html})` : html;
  };
  const freeFactor = label => `(1+${label})`;
  switch (node.type) {
    case "const": return String(node.value);
    case "var": return labels[node.i];
    case "mono": return product(node.indices, labels, label => label);
    case "freeprod": return product(node.indices, labels, freeFactor);
    case "altprod": return `[${product(node.indices, labels, freeFactor)}−1]`;
    case "add": return node.terms.map(parenthesize).join(" + ");
    case "mul": return node.factors.map(parenthesize).join("");
    default: throw new Error("Forma algébrica inválida.");
  }
}

function renderGroupedExpanded(canonical, groups) {
  const grouped = new Map();
  for (const [available, coeff] of canonical) {
    const signature = groups.map(group => group.filter(i => available.includes(i)).length).join(",");
    grouped.set(signature, (grouped.get(signature) || 0) + coeff);
  }
  // Canonical terms arrive in ascending degree, so first occurrence gives
  // deterministic degree order after joining equal exponent vectors.
  const terms = [...grouped].map(([signature, coeff]) => {
    const factors = signature.split(",").map(Number).map((exponent, g) =>
      exponent ? power(groupLabel(groups[g]), exponent) : ""
    ).join("");
    return factors && coeff === 1 ? factors : `${coeff}${factors}`;
  });
  return sum(terms) || "0";
}

// Division-free integer numerator over 100^5, exact in JavaScript's safe integer range.
function computeRNumerator(canonicalPairs, percents) {
  let total = 0;
  for (const [subset, coeff] of canonicalPairs) {
    let term = coeff;
    for (let i = 1; i <= percents.length; i++) {
      term *= subset.includes(i) ? percents[i - 1] : 100 - percents[i - 1];
    }
    total += term;
  }
  return total;
}

function formatPercentBR(numerator) {
  const thousandths = Math.round(numerator / 1e5);
  const integer = Math.floor(thousandths / 1000);
  const fraction = String(thousandths % 1000).padStart(3, "0");
  return fraction === "000" ? `${integer}%` : `${integer},${fraction}%`;
}

function renderPlate(c) {
  get("plate-case").textContent = caseLabel(c);
  get("plate-count").textContent = `${c.states} dos 32 estados`;
  const plot = get("dots");
  const description = [...plot.querySelectorAll("[data-k]")].map(column => {
    const k = Number(column.dataset.k);
    const marks = column.querySelectorAll(".dot");
    marks.forEach((mark, i) => { mark.dataset.success = String(i < c.counts[k]); });
    return `${k} sensores disponíveis: ${c.counts[k]} de ${marks.length} estados com sucesso`;
  });
  plot.setAttribute("aria-label", `Contagem dos 32 estados por cardinalidade. ${description.join(". ")}.`);
}

function renderChart(c, probabilitiesChanged) {
  const chart = get("chart-container");
  const markerFor = key => chart.querySelector(`[data-case="${key}"]`);
  if (probabilitiesChanged) {
    for (const path of chart.querySelectorAll("path[data-tau]")) {
      const coords = nValues.map(n => {
        const key = keyFor(n, path.dataset.tau);
        const mark = markerFor(key);
        const y = ((1e10 - weights.get(key).numerator) / 1e8).toFixed(8);
        mark.setAttribute("y", `${y}%`);
        return `${parseFloat(mark.getAttribute("x"))},${y}`;
      });
      path.setAttribute("d", `M ${coords.join(" L ")}`);
    }
  }
  const selected = markerFor(c.case_key);
  const x = selected.getAttribute("x");
  const y = selected.getAttribute("y");
  get("chart-selected").setAttribute("cx", x);
  get("chart-selected").setAttribute("cy", y);
  get("chart-guide").setAttribute("x1", x);
  get("chart-guide").setAttribute("x2", x);
  get("chart-guide").setAttribute("y1", y);
  const label = `${caseLabel(c)} · R = ${weights.get(c.case_key).percent}`;
  get("chart-case").textContent = label;
  chart.setAttribute("aria-label", `Quatro séries de confiabilidade por tamanho de treino. Ponto selecionado: ${label}. Consulte a tabela para os valores.`);
}

function booleanCondition(minimalSets) {
  return minimalSets.map(group => {
    const joined = group.map(sensor).join(" ∧ ");
    return atom(group.length === 1 ? joined : `(${joined})`);
  }).join(" ∨ ") || "falso";
}

function renderSpecialization(c, groups) {
  const allEqual = groups.length === 1;
  const identity = groups.length === sliders.length;
  const title = get("specialization-title");
  const structured = get("lab-structured-grouped");
  const expanded = get("lab-expanded-grouped");
  const univariate = get("lab-univariate");
  const univariateNote = get("univariate-note");
  const note = get("group-note");
  const hasStates = c.states > 0;

  title.textContent = allEqual ? "Especialização univariada" : "Especialização por disponibilidades iguais";
  structured.hidden = !hasStates || identity;
  expanded.hidden = !hasStates || identity || allEqual;
  univariate.hidden = !hasStates;
  univariateNote.hidden = !hasStates;
  if (identity) {
    note.innerHTML = `Os cinco percentuais são distintos. A substituição é a identidade: cada variável mantém seu índice.
      <a href="#expanded-${c.case_key}" class="to-expanded">Ver a forma geral expandida deste caso</a>.`;
  } else if (allEqual) {
    note.innerHTML = "Os cinco percentuais são iguais. As cinco indeterminadas passam a ser representadas por <i>x</i>.";
  } else {
    const mapping = groups.map(group => atom(`${groupLabel(group)} para ${group.map(sensor).join(", ")}`)).join(" · ");
    note.innerHTML = `As indeterminadas dos sensores com o mesmo percentual passam a compartilhar uma variável. ${mapping}.`;
  }

  if (!hasStates) {
    note.insertAdjacentHTML("beforeend", " A função nula permanece igual sob qualquer substituição, e todos os coeficientes são zero.");
    return;
  }
  if (!identity) {
    const labels = {};
    for (const group of groups) {
      for (const i of group) labels[i] = groupLabel(group);
    }
    structured.innerHTML = `<span class="exprlabel">Forma estruturada</span>${structuredBreaks(renderStructured(c.tree, labels))}`;
    if (!allEqual) {
      expanded.innerHTML = `<span class="exprlabel">Forma expandida</span>${renderGroupedExpanded(c.canonical, groups)}`;
    }
  }
  const label = allEqual ? "Expansão da especialização e projeção univariada" : "Projeção univariada ao igualar todas as indeterminadas a x";
  univariate.innerHTML = `<span class="exprlabel">${label}</span><span class="eqlead">H(x) =</span> ${sum(c.h_univariate_html.split(" + "))}`;
}

function renderScenario(c) {
  const groups = groupsFromValues(state.percents);
  get("current-case").textContent = caseLabel(c);
  get("lab-r-value").textContent = weights.get(c.case_key).percent;
  get("to-current").href = `#row-${c.case_key}`;
  get("lab-condition").innerHTML = booleanCondition(c.minimal_sets);
  const note = get("condition-note");
  if (!c.states) {
    note.textContent = "Nenhum subconjunto avaliado atende à tolerância deste cenário.";
  } else if (c.case_key === "n512-tau0.10") {
    note.innerHTML = "S<sub>2</sub> sozinho basta. Sem ele, S<sub>4</sub> precisa estar disponível com pelo menos um entre S<sub>1</sub>, S<sub>3</sub> e S<sub>5</sub>.";
  } else {
    note.innerHTML = "Cada alternativa é um conjunto mínimo aceitável. Se todos os sensores de alguma alternativa estiverem disponíveis, é possível escolher um preditor que atende à tolerância.";
  }
  get("lab-structured-canonical").innerHTML =
    `<span class="eqlead">H(x<sub>1</sub>, …, x<sub>5</sub>) =</span> ${structuredBreaks(c.h_structured_html)}`;
  renderSpecialization(c, groups);

  const allEqual = groups.length === 1;
  get("lab-r-formula-label").innerHTML = allEqual
    ? '<span class="eqlead">R(p) =</span> <span class="atom"><span class="op">∑<sub>k = 0 a 5</sub></span> a<sub>k</sub>p<sup>k</sup>(1−p)<sup>5−k</sup></span>'
    : '<span class="eqlead">R(<b>p</b>) =</span> <span class="op">∑<sub>A ∈ Ω</sub></span> <span class="atom"><span class="op">∏<sub>i ∈ A</sub></span> p<sub>i</sub></span> <span class="atom"><span class="op">∏<sub>i ∉ A</sub></span> (1−p<sub>i</sub>)</span>';
  get("evaluation-note").innerHTML = allEqual
    ? `Com <i>p</i> = ${state.percents[0]}% para todos os sensores, o peso de cada estado depende apenas de quantos sensores estão disponíveis.`
    : "A soma percorre os estados de sucesso. Cada estado recebe um fator de presença para cada sensor disponível e um fator de ausência para cada sensor indisponível.";
}

function renderTable(c, probabilitiesChanged) {
  if (probabilitiesChanged) {
    for (const [key, value] of weights) get(`r-cell-${key}`).textContent = value.percent;
  }
  const previous = table.querySelector(".selected");
  const selected = get(`row-${c.case_key}`);
  previous?.classList.remove("selected");
  previous?.querySelector(".choose").setAttribute("aria-pressed", "false");
  selected.classList.add("selected");
  selected.querySelector(".choose").setAttribute("aria-pressed", "true");
  get("table-current").textContent = `Seleção atual · ${caseLabel(c)}`;
}

function renderAll(probabilitiesChanged = false) {
  if (probabilitiesChanged) {
    weights = new Map([...cases].map(([key, c]) => {
      const numerator = computeRNumerator(c.canonical, state.percents);
      return [key, {numerator, percent: formatPercentBR(numerator)}];
    }));
  }
  const selected = cases.get(keyFor(state.n, state.tau));
  renderPlate(selected);
  renderScenario(selected);
  renderChart(selected, probabilitiesChanged);
  renderTable(selected, probabilitiesChanged);
}

function selectScenario(n, tau) {
  state.n = n;
  state.tau = tau;
  nSelect.value = String(n);
  tauSelect.value = tau;
  renderAll();
  get("announce").textContent = `Caso selecionado, ${caseLabel(cases.get(keyFor(n, tau)))}.`;
}

function setPercents(percents) {
  state.percents = percents;
  sliders.forEach((input, index) => {
    input.value = percents[index];
    input.setAttribute("aria-valuetext", `${input.value}%`);
    get(`${input.id}-out`).textContent = `${input.value}%`;
  });
  get("preset-all90").setAttribute("aria-pressed", String(percents.every((p, i) => p === defaultPercents[i])));
  get("preset-mixed").setAttribute("aria-pressed", String(percents.every((p, i) => p === mixedPercents[i])));
  renderAll(true);
}

function setDetail(button, open) {
  get(button.getAttribute("aria-controls")).hidden = !open;
  button.setAttribute("aria-expanded", String(open));
  button.firstElementChild.textContent = open ? "−" : "+";
}

function wireDisclosure() {
  table.addEventListener("click", event => {
    const button = event.target.closest(".details-btn");
    if (button) setDetail(button, button.getAttribute("aria-expanded") === "false");
  });
  get("analysis").addEventListener("click", event => {
    const link = event.target.closest(".to-expanded");
    if (!link) return;
    const key = link.hash.slice("#expanded-".length);
    setDetail(get(`row-${key}`).querySelector(".details-btn"), true);
    get(`expanded-${key}`).focus({preventScroll: true});
  });
}

function wireControls() {
  for (const select of [nSelect, tauSelect]) {
    select.addEventListener("change", () => selectScenario(Number(nSelect.value), tauSelect.value));
  }
  for (const input of sliders) {
    input.addEventListener("input", () => setPercents(sliders.map(slider => Number(slider.value))));
  }
  get("preset-all90").addEventListener("click", () => setPercents(defaultPercents));
  get("preset-mixed").addEventListener("click", () => setPercents(mixedPercents));
  table.addEventListener("click", event => {
    const button = event.target.closest(".choose");
    if (button) {
      const {n, tau} = button.closest("tr").dataset;
      selectScenario(Number(n), tau);
    }
  });
  for (const control of [nSelect, tauSelect, ...sliders, get("preset-all90"), get("preset-mixed"), ...table.querySelectorAll(".choose")]) {
    control.disabled = false;
  }
}

async function main() {
  wireDisclosure();
  try {
    const response = await fetch("data/cases.json");
    if (!response.ok) throw new Error();
    const data = await response.json();
    cases = new Map(data.cases.map(c => [c.case_key, c]));
    if (data.cases.length !== nValues.length * taus.length ||
        nValues.some(n => taus.some(tau => !cases.has(keyFor(n, tau))))) {
      throw new Error();
    }
    setPercents(defaultPercents);
    wireControls();
  } catch {
    const message = get("lab-error");
    message.textContent = "Não foi possível carregar os dados dos cenários. Recarregue a página. O cenário inicial e a tabela continuam disponíveis para leitura.";
    message.hidden = false;
  }
}

main();
