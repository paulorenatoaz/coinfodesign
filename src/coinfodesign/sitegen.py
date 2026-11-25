"""Render the static Portuguese report using the cases computed by the build."""
from __future__ import annotations

import math
import re
import shutil
from decimal import Decimal
from html import escape
from pathlib import Path
from string import Template

from . import polynomial, render
from .cases import Case, TAUS
from .data import (
    ARM, CLASSIFIER, LOSS_FILENAME, METADATA_FILENAME, N_VALUES, PINNED_URL_PREFIX,
    SENSOR_NAMES,
)

REPORT = Path(__file__).with_name("report")
DEFAULT_N = 512
DEFAULT_TAU = "0.10"
DEFAULT_PERCENT = 90
CARDINALITIES = tuple(math.comb(len(SENSOR_NAMES), k) for k in range(len(SENSOR_NAMES) + 1))
CODE_REPO = "https://github.com/paulorenatoaz/coinfodesign"

MARKERS = (
    '<rect x="-3" y="-3" width="6" height="6"/>',
    '<circle r="3"/>',
    '<path d="M 0,-4 L 4,0 0,4 -4,0 Z"/>',
    '<path d="M 0,-4 L 4,3 -4,3 Z"/>',
)


def _tau_label(tau: str) -> str:
    return tau.replace(".", ",")


def _case_label(case: dict) -> str:
    return f'n = {case["n_per_class"]} · τ = {_tau_label(case["tau"])}'


def _case_key(n: int, tau: str) -> str:
    return f"n{n}-tau{tau}"


def _boolean_condition(minimal_sets: list[list[int]]) -> str:
    parts = []
    for sensors in minimal_sets:
        term = " ∧ ".join(f"S<sub>{i}</sub>" for i in sensors)
        if len(sensors) > 1:
            term = f"({term})"
        parts.append(f'<span class="atom">{term}</span>')
    return " ∨ ".join(parts) if parts else "falso"


def _structured_breaks(html: str) -> str:
    # Products can break between complete factors. Indices stay with their variables.
    return re.sub(r"(</sub>|</sup>|[)\]])(?=[x(\[])", r"\1<wbr>", html)


def _sum_breaks(html: str) -> str:
    return " + ".join(f'<span class="atom">{term}</span>' for term in html.split(" + "))


def _dotplot(counts: list[int]) -> str:
    description = ". ".join(
        f"{k} sensores disponíveis: {count} de {total} estados com sucesso"
        for k, (count, total) in enumerate(zip(counts, CARDINALITIES))
    )
    columns = []
    for k, (count, total) in enumerate(zip(counts, CARDINALITIES)):
        dots = "".join(f'<i class="dot" data-success="{str(i < count).lower()}"></i>' for i in range(total))
        columns.append(
            f'<div class="dotcolumn" data-k="{k}"><div class="dots">{dots}</div><b>{k}</b></div>'
        )
    return (
        '<div id="dots" role="img" '
        f'aria-label="Contagem dos 32 estados por cardinalidade. {description}.">'
        f'<div class="dotplot" aria-hidden="true">{"".join(columns)}</div></div>'
    )


def _plot_coordinates(case: dict) -> tuple[float, Decimal]:
    x = 100 * N_VALUES.index(case["n_per_class"]) / (len(N_VALUES) - 1)
    y = 100 * (1 - Decimal(case["r_at_90"]))
    return x, y


def _chart(cases: dict, selected: dict) -> tuple[str, str]:
    # A normalized SVG layer keeps the lines responsive. An unscaled overlay
    # holds the marks, so their shapes and strokes stay legible on phones.
    paths, marks, legend = [], [], []
    for i, tau in enumerate(TAUS):
        tau_key = f"{tau:.2f}"
        keys = [_case_key(n, tau_key) for n in N_VALUES]
        coords = [_plot_coordinates(cases[key]) for key in keys]
        path = "M " + " L ".join(f"{x:.6f},{y:f}" for x, y in coords)
        paths.append(f'<g class="chart-series series-{i}"><path data-tau="{tau_key}" d="{path}"/></g>')
        marks.extend(
            f'<use class="chart-mark series-{i}" data-case="{key}" href="#marker-{i}" x="{x:.6f}%" y="{y:f}%"/>'
            for key, (x, y) in zip(keys, coords)
        )
        legend.append(
            f'<span><svg class="series-{i}" viewBox="0 0 36 14" aria-hidden="true">'
            f'<line class="chart-series" x2="36" y1="7" y2="7"/>'
            f'<use class="marker" href="#marker-{i}" x="18" y="7"/></svg> τ = {_tau_label(tau_key)}</span>'
        )
    definitions = "".join(f'<g id="marker-{i}">{marker}</g>' for i, marker in enumerate(MARKERS))
    grid = "".join(f'<line class="chart-grid" x2="100" y1="{y}" y2="{y}"/>' for y in range(0, 101, 25))
    y_ticks = "".join(
        f'<span class="chart-tick y-tick" style="top:{100 - pct}%">{pct}</span>' for pct in range(100, -1, -25)
    )
    x_ticks = "".join(
        f'<span class="chart-tick x-tick{" minor-tick" if i in (1, 3, 5, 7, 8) else ""}" '
        f'style="left:{100 * i / (len(N_VALUES) - 1):.6f}%">{n}</span>' for i, n in enumerate(N_VALUES)
    )
    x, y = _plot_coordinates(selected)
    chart = f"""
      <div id="chart-container" class="chart-plot" role="img"
           aria-label="Quatro séries de confiabilidade por tamanho de treino. Ponto selecionado: {_case_label(selected)} · R = {selected['r_at_90_br']}. Consulte a tabela para os valores.">
        <svg id="chart-svg" aria-hidden="true">
          <defs>{definitions}</defs>
          <svg class="plot-layer" viewBox="0 0 100 100" preserveAspectRatio="none">{grid}{"".join(paths)}</svg>
          <line id="chart-guide" class="chart-guide" x1="{x:.6f}%" x2="{x:.6f}%" y1="{y:f}%" y2="100%"/>
          {"".join(marks)}
          <circle id="chart-selected" class="chart-ring" cx="{x:.6f}%" cy="{y:f}%" r="7"/>
        </svg>
        <div aria-hidden="true">{y_ticks}{x_ticks}</div>
      </div>"""
    return chart, "".join(legend)


def _case_row(case: dict, selected: dict) -> str:
    n, tau, key = case["n_per_class"], case["tau"], case["case_key"]
    is_selected = case is selected
    condition = _boolean_condition(case["minimal_sets"])
    counts = " · ".join(str(v) for v in case["counts"])
    univariate = _sum_breaks(case["h_univariate_html"])
    cls = " ".join(label for label, show in (("group-start", tau == "0.02"), ("selected", is_selected)) if show)
    return f"""
        <tr id="row-{key}" class="{cls}" data-n="{n}" data-tau="{tau}" tabindex="-1">
          <th scope="row" class="numeric"><button type="button" class="choose" disabled
            aria-pressed="{str(is_selected).lower()}" aria-label="Selecionar caso, {_case_label(case)}">{n}</button></th>
          <td class="numeric">{_tau_label(tau)}</td>
          <td class="extra cellmath">{condition}</td>
          <td class="numeric">{case['states']}</td>
          <td class="extra counts">{counts}</td>
          <td class="extra cellmath">{univariate}</td>
          <td class="numeric" id="r-cell-{key}">{case['r_at_90_br']}</td>
          <td class="right"><button type="button" class="details-btn" aria-expanded="false" aria-controls="detail-{key}"
            aria-label="Detalhes do caso, {_case_label(case)}"><span aria-hidden="true">+</span></button></td>
        </tr>
        <tr id="detail-{key}" hidden><td class="detailcell" colspan="8">
          <div class="detail-extra">
            <p><strong>Condição de sucesso</strong></p><div class="equation">{condition}</div>
            <p><strong>Coeficientes a<sub>0</sub> a a<sub>5</sub></strong> ({counts})</p>
            <div class="equation"><span class="eqlead">H(x) =</span> {univariate}</div>
          </div>
          <p class="exprlabel">Forma geral estruturada</p>
          <div class="equation"><span class="eqlead">H(x<sub>1</sub>, …, x<sub>5</sub>) =</span> {_structured_breaks(case['h_structured_html'])}</div>
          <p class="exprlabel" id="expanded-label-{key}">Forma geral expandida</p>
          <div class="equation" id="expanded-{key}" tabindex="-1" aria-labelledby="expanded-label-{key}"><span class="eqlead">H(x<sub>1</sub>, …, x<sub>5</sub>) =</span> {_sum_breaks(case['h_expanded_html'])}</div>
        </td></tr>"""


def _cases_table(cases: list[dict], selected: dict) -> str:
    rows = "".join(_case_row(case, selected) for case in cases)
    return f"""<table id="panorama-table">
        <caption class="sr">Quarenta cenários com a confiabilidade para as disponibilidades atuais</caption>
        <colgroup>
          <col class="col-n"><col class="col-t"><col class="extra col-rule"><col class="col-st">
          <col class="extra col-count"><col class="extra col-h"><col class="col-r"><col class="col-det">
        </colgroup>
        <thead><tr>
          <th scope="col" class="numeric"><i>n</i></th><th scope="col" class="numeric"><i>τ</i></th>
          <th scope="col" class="extra">Condição de sucesso</th><th scope="col" class="numeric">Estados</th>
          <th scope="col" class="extra">Coeficientes<br><span>a<sub>0</sub> … a<sub>5</sub></span></th>
          <th scope="col" class="extra">H(x)</th><th scope="col" class="numeric"><i>R</i></th>
          <th scope="col" class="right"><span class="wide">Detalhes</span><span class="narrow">Ver</span></th>
        </tr></thead><tbody>{rows}
        </tbody>
      </table>"""


def _plateau_table(starts: dict) -> str:
    rows = "".join(
        f'<tr><th scope="row">{_tau_label(tau)}</th><td>{n}</td></tr>' for tau, n in starts.items()
    )
    return (
        '<table><caption>Início do platô por tolerância</caption><thead>'
        '<tr><th scope="col">Tolerância <i>τ</i></th><th scope="col">Primeiro <i>n</i></th></tr></thead>'
        f'<tbody>{rows}</tbody></table>'
    )


def _options(values, selected, label=str) -> str:
    return "".join(
        f'<option value="{value}"{" selected" if value == selected else ""}>{label(value)}</option>'
        for value in values
    )


def _sliders() -> str:
    return "\n".join(
        f'<div class="slider-row"><label for="p{i}"><b>S<sub>{i}</sub></b> {name}</label>'
        f'<input type="range" id="p{i}" min="0" max="100" step="1" value="{DEFAULT_PERCENT}" '
        f'aria-valuetext="{DEFAULT_PERCENT}%" disabled>'
        f'<output id="p{i}-out" for="p{i}" aria-live="off">{DEFAULT_PERCENT}%</output></div>'
        for i, name in enumerate(SENSOR_NAMES, start=1)
    )


def generate(out_dir: Path, payload: dict, build_commit: str, computed_cases: list[Case]) -> None:
    assets = out_dir / "assets"
    shutil.copytree(REPORT / "fonts", assets / "fonts")
    for filename in ("style.css", "app.js"):
        shutil.copyfile(REPORT / filename, assets / filename)

    cases = {case["case_key"]: case for case in payload["cases"]}
    selected = cases[_case_key(DEFAULT_N, DEFAULT_TAU)]
    chart, legend = _chart(cases, selected)
    source = payload["source"]
    source_path = PINNED_URL_PREFIX.split(f'/{source["commit"]}/')[1].rstrip("/")
    code_url = CODE_REPO
    if re.fullmatch(r"[0-9a-f]{12,40}", build_commit):
        code_url += f"/tree/{build_commit}"

    # The existing formula renderers also serve the machine-readable exports.
    # The report alone adds line-breaking opportunities.
    equal = render.labels_from_groups([polynomial.UNIVERSE])
    selected_case = next(case for case in computed_cases if case.case_key == selected["case_key"])
    template = Template((REPORT / "index.html").read_text(encoding="utf-8"))
    html = template.substitute(
        case_label=_case_label(selected),
        case_key=selected["case_key"],
        states=selected["states"],
        dotplot=_dotplot(selected["counts"]),
        n_options=_options(N_VALUES, DEFAULT_N),
        tau_options=_options([f"{tau:.2f}" for tau in TAUS], DEFAULT_TAU, _tau_label),
        sliders=_sliders(),
        reliability=selected["r_at_90_br"],
        condition=_boolean_condition(selected["minimal_sets"]),
        condition_note="S<sub>2</sub> sozinho basta. Sem ele, S<sub>4</sub> precisa estar disponível com pelo menos um entre S<sub>1</sub>, S<sub>3</sub> e S<sub>5</sub>.",
        h_structured=_structured_breaks(selected["h_structured_html"]),
        h_equal_structured=_structured_breaks(render.render_structured_html(selected_case.tree, equal)),
        h_univariate=_sum_breaks(selected["h_univariate_html"]),
        chart=chart,
        legend=legend,
        cases_table=_cases_table(payload["cases"], selected),
        plateau_table=_plateau_table(payload["plateau_start_n"]),
        run=escape(source["run"]),
        arm=ARM,
        classifier=CLASSIFIER,
        source_commit=escape(source["commit"]),
        source_url=f'https://github.com/{source["repo"]}/tree/{source["commit"]}/{source_path}',
        loss_url=PINNED_URL_PREFIX + LOSS_FILENAME,
        metadata_url=PINNED_URL_PREFIX + METADATA_FILENAME,
        code_url=code_url,
        build_id=escape(build_commit),
    )
    (out_dir / "index.html").write_text(html, encoding="utf-8")
    (out_dir / "build_id.txt").write_text(build_commit + "\n", encoding="utf-8")
