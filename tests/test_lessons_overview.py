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


def create_user(conn):
	with conn.cursor() as cur:
		email = f"t-{uuid.uuid4().hex[:8]}@example.com"
		cur.execute("INSERT INTO app_user (email) VALUES (%s) RETURNING id", (email,))
		return cur.fetchone()[0]


def ensure_seed_lessons(conn):
	"""Insert minimal lessons covering grammar and vocabulary emoji/prefixes if none exist."""
	with conn.cursor() as cur:
		cur.execute("SELECT COUNT(*) FROM lesson")
		count = cur.fetchone()[0]
		if count == 0:
			cur.execute("INSERT INTO lesson (title, topic) VALUES ('G1', '📚 Grammar Basics')")
			cur.execute("INSERT INTO lesson (title, topic) VALUES ('G2', '🛠 Tools of Grammar')")
			cur.execute("INSERT INTO lesson (title, topic) VALUES ('V1', '🧠 Vocabulary Starter')")
			cur.execute("INSERT INTO lesson (title, topic) VALUES ('V2', 'Vocab: Animals')")


def test_lessons_overview_returns_grammar(conn, api_client):
	ensure_seed_lessons(conn)
	user_id = create_user(conn)
	r = api_client.get(f"/lessons/overview", params={"user_id": user_id, "group": "grammar"})
	assert r.status_code == 200
	data = r.json()
	assert data.get("group") == "grammar"
	lessons = data.get("lessons", [])
	assert len(lessons) > 0
	# At least one should have a grammar emoji/prefix
	assert any(l["topic"].startswith(("📚", "📌", "🧱", "🛠", "🚫", "Grammar")) for l in lessons if l["topic"]) 


def test_lessons_overview_returns_vocabulary(conn, api_client):
	ensure_seed_lessons(conn)
	user_id = create_user(conn)
	r = api_client.get(f"/lessons/overview", params={"user_id": user_id, "group": "vocabulary"})
	assert r.status_code == 200
	data = r.json()
	assert data.get("group") == "vocabulary"
	lessons = data.get("lessons", [])
	assert len(lessons) > 0
	# At least one should have a vocabulary emoji/prefix
	assert any(l["topic"].startswith(("🧠", "Vocabulary", "Vocab")) for l in lessons if l["topic"]) 

