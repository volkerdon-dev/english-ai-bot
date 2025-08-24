import os
import time

import pytest
import psycopg
import uuid


DB_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/appdb")


def pg_native_url(url: str) -> str:
    # Convert SQLAlchemy URL to native psycopg URL if needed
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


def create_user_lesson_task(cur):
    email = f"u-{uuid.uuid4().hex[:8]}@example.com"
    cur.execute("INSERT INTO app_user (email) VALUES (%s) RETURNING id", (email,))
    user_id = cur.fetchone()[0]

    cur.execute("INSERT INTO lesson (title, topic) VALUES ('L1', 'grammar') RETURNING id")
    lesson_id = cur.fetchone()[0]

    cur.execute("""
        INSERT INTO task (lesson_id, content, answer, topic)
        VALUES (%s, '{"q": "x"}'::jsonb, '{"a": "y"}'::jsonb, 'grammar') RETURNING id
    """, (lesson_id,))
    task_id = cur.fetchone()[0]
    return user_id, lesson_id, task_id


def insert_attempt(cur, user_id, task_id, is_correct):
    cur.execute(
        "INSERT INTO task_attempt (user_id, task_id, is_correct, response) VALUES (%s, %s, %s, '{"r":1}'::jsonb) RETURNING id",
        (user_id, task_id, is_correct),
    )
    return cur.fetchone()[0]


def fetch_progress(cur, user_id, lesson_id):
    cur.execute(
        "SELECT attempts, correct, accuracy, mastered FROM lesson_progress WHERE user_id=%s AND lesson_id=%s",
        (user_id, lesson_id),
    )
    return cur.fetchone()


def fetch_topic_stats(cur, user_id, topic):
    cur.execute(
        "SELECT attempts, correct, accuracy FROM topic_stats WHERE user_id=%s AND topic=%s",
        (user_id, topic),
    )
    return cur.fetchone()


def test_mastered_by_three_in_a_row(conn):
    with conn.cursor() as cur:
        user_id, lesson_id, task_id = create_user_lesson_task(cur)
        insert_attempt(cur, user_id, task_id, True)
        insert_attempt(cur, user_id, task_id, True)
        insert_attempt(cur, user_id, task_id, True)

        attempts, correct, accuracy, mastered = fetch_progress(cur, user_id, lesson_id)
        assert mastered is True

        ats, cor, acc = fetch_topic_stats(cur, user_id, 'grammar')
        assert ats == attempts and cor == correct
        assert round(acc, 2) == round(accuracy, 2)


def test_mastered_by_accuracy_threshold(conn):
    with conn.cursor() as cur:
        user_id, lesson_id, task_id = create_user_lesson_task(cur)
        # 9 correct out of 10
        for i in range(9):
            insert_attempt(cur, user_id, task_id, True)
        insert_attempt(cur, user_id, task_id, False)

        attempts, correct, accuracy, mastered = fetch_progress(cur, user_id, lesson_id)
        assert attempts >= 10
        assert correct >= 9
        assert accuracy >= 0.9
        assert mastered is True

