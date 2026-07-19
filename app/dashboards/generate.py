from __future__ import annotations

import json
from pathlib import Path

from grafanalib._gen import DashboardEncoder

from app.dashboards.papergraph import DASHBOARDS

OUTPUT_DIR = Path("infra/monitoring/grafana/dashboards")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for dashboard_file in DASHBOARDS:
        output_path = OUTPUT_DIR / dashboard_file.name
        if hasattr(dashboard_file.dashboard, "to_json_data"):
            dashboard_json = dashboard_file.dashboard.to_json_data()
        else:
            dashboard_json = dashboard_file.dashboard
        output_path.write_text(
            json.dumps(dashboard_json, cls=DashboardEncoder, indent=2, sort_keys=True) + "\n"
        )
        print(output_path)


if __name__ == "__main__":
    main()
