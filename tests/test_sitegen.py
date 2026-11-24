import json

import pytest

from coinfodesign.build import build


@pytest.fixture(scope="module")
def built_site(dataset, tmp_path_factory):
    out = tmp_path_factory.mktemp("site")
    payload = build(None, out, "test-commit-abc123")
    return out, payload


def test_build_produces_expected_layout(built_site):
    out, payload = built_site
    assert (out / "index.html").is_file()
    assert (out / "data" / "cases.json").is_file()
    assert (out / "data" / "cases.csv").is_file()
    assert (out / "LICENSE").is_file()
    assert (out / "ATTRIBUTION.md").is_file()
    assert (out / "CITATION.cff").is_file()
    assert payload["case_count"] == 40


def test_site_is_a_single_unified_page_not_two_experiences(built_site):
    out, _ = built_site
    html = (out / "index.html").read_text(encoding="utf-8")
    # One shared control set drives everything; no separate "laboratory" page/section.
    assert "Parte A" not in html
    assert "Parte B" not in html
    assert 'id="n-select"' in html
    assert 'id="tau-select"' in html
    for i in range(1, 6):
        assert f'id="p{i}"' in html
    assert html.count('id="n-select"') == 1
    assert html.count('id="tau-select"') == 1


def test_table_rows_are_clickable_and_carry_scenario_keys(built_site):
    out, payload = built_site
    html = (out / "index.html").read_text(encoding="utf-8")
    for case in payload["cases"]:
        key = case["case_key"]
        assert f'id="row-{key}"' in html
        assert f'data-n="{case["n_per_class"]}"' in html
        assert f'id="r-cell-{key}"' in html
    assert 'tabindex="0"' in html


def test_app_js_has_reactive_wiring(built_site):
    out, _ = built_site
    js = (out / "assets" / "app.js").read_text(encoding="utf-8")
    for fn in ("renderAll", "renderChart", "renderScenario", "renderTable", "selectScenario", "computeRNumerator"):
        assert fn in js


def test_cases_json_has_canonical_data_for_client_side_recomputation(built_site):
    out, _ = built_site
    data = json.loads((out / "data" / "cases.json").read_text(encoding="utf-8"))
    assert len(data["cases"]) == 40
    classroom = next(c for c in data["cases"] if c["case_key"] == "n512-tau0.10")
    assert classroom["r_at_90_br"] == "98,991%"
    assert classroom["counts"] == [0, 1, 7, 9, 5, 1]
    assert classroom["tree"]["type"] in ("add", "mul", "freeprod", "const")
    assert len(classroom["canonical"]) == 23
