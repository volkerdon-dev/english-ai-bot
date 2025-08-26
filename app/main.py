import os
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
import logging
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


logger = logging.getLogger("app")


@app.exception_handler(Exception)
async def all_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url)
    return JSONResponse(status_code=500, content={"detail": "internal_error"})


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
                INSERT INTO task_attempt (user_id, task_id, lesson_id, response, is_correct)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
                """,
                (a.user_id, a.task_id, lesson_id, Json(a.response), a.is_correct),
            )
            attempt_id = cur.fetchone()[0]

            cur.execute(
                """
                SELECT attempts, correct, mastered,
                       CASE WHEN attempts>0 THEN correct::float/attempts ELSE 0 END AS accuracy
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
                SELECT l.id, l.title,
                       lp.attempts, lp.correct, lp.mastered,
                       CASE WHEN lp.attempts>0 THEN lp.correct::float/lp.attempts ELSE 0 END AS accuracy
                FROM lesson_progress lp
                JOIN lesson l ON l.id = lp.lesson_id
                WHERE lp.user_id=%s
                ORDER BY lp.mastered DESC, lp.updated_at DESC NULLS LAST
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
                SELECT topic_code, subtopic_code, attempts, correct,
                       CASE WHEN attempts>0 THEN correct::float/attempts ELSE 0 END AS accuracy
                FROM topic_stats
                WHERE user_id=%s AND attempts >= 10
                ORDER BY accuracy ASC, attempts DESC
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


@app.get("/")
def root():
    return {"ok": True}


if __name__ == "__main__":
    import os as _os
    import uvicorn as _uvicorn
    _port = int(_os.getenv("PORT", "8000"))
    _uvicorn.run("app.main:app", host="0.0.0.0", port=_port)
