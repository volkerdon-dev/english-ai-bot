import os
from typing import Optional, List
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import psycopg
from psycopg.types.json import Json

DB_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/appdb")
DB_URL = DB_URL.replace("postgresql+psycopg://", "postgresql://")  # psycopg native

app = FastAPI(title="English AI Bot API")


class AttemptIn(BaseModel):
    user_id: int
    task_id: int
    lesson_id: Optional[int] = None
    is_correct: bool
    score: Optional[float] = None
    response: dict = Field(default_factory=dict)
    error_tags: List[str] = Field(default_factory=list)


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/attempts")
def create_attempt(a: AttemptIn):
    with psycopg.connect(DB_URL, autocommit=True) as conn:
        with conn.cursor() as cur:
            lesson_id = a.lesson_id
            if lesson_id is None:
                cur.execute("SELECT lesson_id FROM task WHERE id=%s", (a.task_id,))
                row = cur.fetchone()
                if not row:
                    raise HTTPException(400, "task_id not found")
                lesson_id = row[0]

            cur.execute(
                """
                INSERT INTO task_attempt
                (user_id, task_id, lesson_id, started_at, finished_at, client_latency_ms, response, is_correct, score, error_tags)
                VALUES (%s,%s,%s, NOW(), NOW(), %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (a.user_id, a.task_id, lesson_id, 0, Json(a.response), a.is_correct, a.score, a.error_tags),
            )
            attempt_id = cur.fetchone()[0]

            cur.execute(
                """
                SELECT attempts_total, correct_total, mastered,
                       CASE WHEN attempts_total>0 THEN correct_total::float/attempts_total ELSE 0 END AS accuracy
                FROM lesson_progress
                WHERE user_id=%s AND lesson_id=%s
                """,
                (a.user_id, lesson_id),
            )
            row = cur.fetchone()
            progress = None
            if row:
                progress = {
                    "attempts_total": row[0],
                    "correct_total": row[1],
                    "mastered": row[2],
                    "accuracy": float(row[3]),
                }

    return {"attemptId": attempt_id, "lessonId": lesson_id, "progress": progress}


@app.get("/progress/summary")
def summary(user_id: int):
    with psycopg.connect(DB_URL, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT l.id, l.title, lp.attempts_total, lp.correct_total, lp.mastered,
                       CASE WHEN lp.attempts_total>0 THEN lp.correct_total::float/lp.attempts_total ELSE 0 END AS accuracy
                FROM lesson_progress lp
                JOIN lesson l ON l.id = lp.lesson_id
                WHERE lp.user_id=%s
                ORDER BY lp.mastered DESC, lp.last_seen_at DESC
                """,
                (user_id,),
            )
            lessons = [
                {
                    "lesson_id": r[0],
                    "title": r[1],
                    "attempts_total": r[2],
                    "correct_total": r[3],
                    "mastered": r[4],
                    "accuracy": float(r[5]),
                }
                for r in cur.fetchall()
            ]
            cur.execute(
                """
                SELECT topic_code, subtopic_code, attempts_total, correct_total,
                       CASE WHEN attempts_total>0 THEN correct_total::float/attempts_total ELSE 0 END AS accuracy
                FROM topic_stats
                WHERE user_id=%s AND attempts_total >= 10
                ORDER BY accuracy ASC, attempts_total DESC
                LIMIT 5
                """,
                (user_id,),
            )
            weak = [
                {
                    "topic": r[0],
                    "subtopic": r[1],
                    "attempts": r[2],
                    "correct": r[3],
                    "accuracy": float(r[4]),
                }
                for r in cur.fetchall()
            ]
    return {"lessons": lessons, "weakSubtopics": weak}

