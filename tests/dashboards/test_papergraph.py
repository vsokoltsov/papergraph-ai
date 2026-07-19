from __future__ import annotations

import json

from grafanalib._gen import DashboardEncoder

from app.dashboards import generate
from app.dashboards.papergraph import DASHBOARDS


def encoded_dashboard(dashboard_file) -> dict:
    return json.loads(json.dumps(dashboard_file.dashboard.to_json_data(), cls=DashboardEncoder))


def test_dashboards_use_expected_defaults() -> None:
    dashboards = [encoded_dashboard(dashboard_file) for dashboard_file in DASHBOARDS]

    assert len(dashboards) == 5

    for dashboard in dashboards:
        assert dashboard["timezone"] == "browser"
        assert dashboard["refresh"] == "10s"
        assert dashboard["time"] == {"from": "now-5m", "to": "now"}
        assert dashboard["tags"]
        assert dashboard["panels"]


def test_dashboards_include_different_panel_types() -> None:
    panel_types = {
        panel["type"]
        for dashboard_file in DASHBOARDS
        for panel in encoded_dashboard(dashboard_file)["panels"]
    }

    assert {
        "barchart",
        "bargauge",
        "gauge",
        "piechart",
        "stat",
        "table",
        "timeseries",
    }.issubset(panel_types)


def test_dashboard_panels_use_prometheus_datasource() -> None:
    for dashboard_file in DASHBOARDS:
        dashboard = encoded_dashboard(dashboard_file)

        for panel in dashboard["panels"]:
            assert panel["datasource"] == {"type": "prometheus", "uid": "Prometheus"}
            assert panel["targets"]
            assert panel["targets"][0]["expr"]


def test_generate_writes_dashboard_json_files(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(generate, "OUTPUT_DIR", tmp_path)

    generate.main()

    output_files = sorted(tmp_path.glob("*.json"))
    assert [output_file.name for output_file in output_files] == sorted(
        dashboard_file.name for dashboard_file in DASHBOARDS
    )

    for output_file in output_files:
        dashboard = json.loads(output_file.read_text())
        assert dashboard["uid"]
        assert dashboard["title"].startswith("PaperGraph")
        assert dashboard["time"] == {"from": "now-5m", "to": "now"}
