import os
import time
import uuid
import psycopg
import pytest
 

DB_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/appdb")
 


def pg_native_url(url: str) -> str:
    return url.replace("postgresql+psycopg://", "postgresql://")


def wait_for_db(conninfo: str, timeout: float = 30.0) -> None:
    start = time.time()
    while True:
        try:
            with psycopg.connect(conninfo, connect_timeout=2) as _:
                return
        except Exception:
            if time.time() - start > timeout:
                raise
            time.sleep(0.5)


@pytest.fixture(scope="module")
def conn():
    url = pg_native_url(DB_URL)
    wait_for_db(url)
    with psycopg.connect(url, autocommit=True) as c:
        yield c


def ensure_seed_tree(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM lesson")
        count = cur.fetchone()[0]
        if count == 0:
            # Grammar
            cur.execute("INSERT INTO lesson (title, topic) VALUES ('Present Simple Intro', '📚 Tenses / Present / Present Simple')")
            cur.execute("INSERT INTO lesson (title, topic) VALUES ('Past Simple Intro', '📚 Tenses / Past / Past Simple')")
            # Vocabulary
            cur.execute("INSERT INTO lesson (title, topic) VALUES ('Animals A1', '🧠 Animals / Mammals / Cats')")


def test_catalog_tree_grammar(conn, api_client):
    ensure_seed_tree(conn)
    r = api_client.get("/catalog/tree", params={"group": "grammar"})
    assert r.status_code == 200
    data = r.json()
    assert data.get("group") == "grammar"
    sections = data.get("sections", [])
    assert isinstance(sections, list) and len(sections) > 0
    # ensure 3-level presence
    any_unit = False
    for s in sections:
        for sub in s.get("subsections", []):
            if sub.get("units"):
                any_unit = True
    assert any_unit


def test_lessons_overview_filtering(conn, api_client):
    r = api_client.get("/lessons/overview", params={
        "user_id": 1,
        "group": "grammar",
        "section": "Tenses",
        "subsection": "Present"
    })
    assert r.status_code == 200
    data = r.json()
    assert data.get("group") == "grammar"
    assert isinstance(data.get("lessons"), list)
