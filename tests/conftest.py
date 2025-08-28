import os
import pytest
import httpx
from httpx import ASGITransport

# Set DATABASE_URL for tests before importing the app
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/appdb")
os.environ.setdefault("ADMIN_TOKEN", "test_admin_token")

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def api_client():
    transport = ASGITransport(app=app)
    with httpx.Client(transport=transport, base_url="http://testserver", timeout=10.0) as client:
        yield client

