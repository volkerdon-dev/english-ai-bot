import httpx
from httpx import ASGITransport

from app.main import app, conn
from psycopg.rows import dict_row


def test_auth_tg_creates_or_returns_user():
    client = httpx.Client(transport=ASGITransport(app=app), base_url="http://testserver", timeout=10.0)
    tg_user_id = 123456789

    r1 = client.post("/auth/tg", json={"tg_user_id": tg_user_id})
    assert r1.status_code == 200
    data1 = r1.json()
    assert data1["tgUserId"] == tg_user_id
    uid = data1["userId"]

    r2 = client.post("/auth/tg", json={"tg_user_id": tg_user_id})
    assert r2.status_code == 200
    data2 = r2.json()
    assert data2["userId"] == uid
    assert data2["plan"] in ("free", "pro")

    if conn is not None:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT id, tg_user_id FROM app_user WHERE id=%s", (uid,))
            row = cur.fetchone()
            assert row and row["tg_user_id"] == tg_user_id

