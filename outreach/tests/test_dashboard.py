from pathlib import Path

from fastapi.testclient import TestClient

from eliora_outreach.config import Settings
from eliora_outreach.dashboard.app import create_app
from eliora_outreach.db import Database


def test_dashboard_routes_are_local_and_escape_untrusted_content(tmp_path: Path) -> None:
    app = create_app(Settings(), Database(tmp_path / "dashboard.sqlite3"))
    client = TestClient(app)
    for path in ("/", "/leads", "/drafts", "/messages", "/suppressions", "/runs", "/settings"):
        response = client.get(path)
        assert response.status_code == 200
        assert "EliOra Outreach" in response.text
    assert client.post("/pause", data={"csrf_token": "wrong"}).status_code == 403
