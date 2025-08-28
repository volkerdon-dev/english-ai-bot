import os
import psycopg


DB_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/appdb").replace("postgresql+psycopg://", "postgresql://")


def test_admin_seed_and_tree(api_client):
    # trigger seeding
    r = api_client.post("/admin/seed/demo", headers={"X-Admin-Token": os.getenv("ADMIN_TOKEN", "")})
    assert r.status_code == 200
    data = r.json()
    assert data["lessons_added"] >= 0  # idempotent

    # verify counts in DB
    with psycopg.connect(DB_URL, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM lesson")
            lessons_cnt = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM task")
            tasks_cnt = cur.fetchone()[0]
            assert lessons_cnt >= 10
            assert tasks_cnt >= 30

    # catalog tree for grammar
    r2 = api_client.get("/catalog/tree", params={"group": "grammar"})
    assert r2.status_code == 200
    tree = r2.json()
    assert tree.get("sections")
    # at least one unit exists
    assert any(len(sub.get("units", [])) > 0 for sec in tree["sections"] for sub in sec.get("subsections", []))


def test_overview_and_attempt_updates_topic(api_client):
    # overview should not be empty for grammar
    r = api_client.get("/lessons/overview", params={"group": "grammar"})
    assert r.status_code == 200
    ov = r.json()
    assert ov.get("lessons")

    # find a task to attempt
    # pick the first lesson id from tree and fetch next task
    rtree = api_client.get("/catalog/tree", params={"group": "grammar"})
    lesson_id = None
    for sec in rtree.json().get("sections", []):
        for sub in sec.get("subsections", []):
            for unit in sub.get("units", []):
                ids = unit.get("lessonIds") or []
                if ids:
                    lesson_id = ids[0]
                    break
            if lesson_id:
                break
        if lesson_id:
            break
    assert lesson_id is not None

    # create a user
    with psycopg.connect(DB_URL, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO app_user (email) VALUES ('seedtest@example.com') RETURNING id")
            user_id = cur.fetchone()[0]

    # fetch next task
    rtask = api_client.get("/tasks/next", params={"lesson_id": lesson_id, "user_id": user_id})
    assert rtask.status_code == 200
    task_id = rtask.json()["task_id"]

    # submit attempt
    ratt = api_client.post("/attempts", json={"user_id": user_id, "task_id": task_id, "is_correct": True, "response": {}})
    assert ratt.status_code == 200

    # topic_stats should reflect lesson topic and not 'unknown'
    with psycopg.connect(DB_URL, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT topic FROM lesson WHERE id=%s", (lesson_id,))
            topic = cur.fetchone()[0]
            cur.execute("SELECT topic FROM topic_stats WHERE user_id=%s ORDER BY id DESC LIMIT 1", (user_id,))
            ts_topic = cur.fetchone()[0]
            assert ts_topic == (topic or ts_topic)
            assert ts_topic != 'unknown'

