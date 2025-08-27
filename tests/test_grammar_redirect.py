import os
import sys
from fastapi.testclient import TestClient

# Ensure workspace root is importable so `app` package resolves
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from app.main import app


def test_grammar_redirect_returns_ok_without_json_404():
    client = TestClient(app)
    # Follow redirects to ensure final page is reachable (200)
    r = client.get("/grammar", allow_redirects=True)
    assert r.status_code == 200
    # Should not be FastAPI JSON 404 body
    assert not (r.headers.get("content-type", "").startswith("application/json") and r.json().get("detail") == "Not Found")
