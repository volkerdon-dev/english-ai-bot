import os
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import logging
from pydantic import BaseModel, Field
import psycopg
from psycopg.types.json import Json

DB_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/appdb")
DB_URL = DB_URL.replace("postgresql+psycopg://", "postgresql://")  # psycopg native

app = FastAPI(title="English AI Bot API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AttemptIn(BaseModel):
    user_id: int
    task_id: int
    lesson_id: Optional[int] = None
    is_correct: bool
    score: Optional[float] = None
    response: dict = Field(default_factory=dict)
    error_tags: List[str] = Field(default_factory=list)


class AuthTgIn(BaseModel):
    tg_user_id: int


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
            # Get lesson_id from task table (do NOT insert lesson_id into task_attempt)
            cur.execute("SELECT lesson_id FROM task WHERE id=%s", (a.task_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(400, "task_id not found")
            lesson_id = row[0]

            # Minimal insert: only existing columns in your DB
            cur.execute("""
                INSERT INTO task_attempt (user_id, task_id, response, is_correct)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            """, (a.user_id, a.task_id, Json(a.response), a.is_correct))
            attempt_id = cur.fetchone()[0]

            # Read progress from your schema (attempts/correct/mastered), no last_seen_at
            cur.execute("""
                SELECT attempts, correct, mastered,
                       CASE WHEN attempts>0 THEN correct::float/attempts ELSE 0 END AS accuracy
                FROM lesson_progress
                WHERE user_id=%s AND lesson_id=%s
            """, (a.user_id, lesson_id))
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


@app.post("/auth/tg")
def auth_tg(payload: AuthTgIn):
    # Create or get a user bound to Telegram ID
    email = f"tg-{payload.tg_user_id}@tg.local"
    with psycopg.connect(DB_URL, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO app_user (email)
                VALUES (%s)
                ON CONFLICT (email) DO UPDATE SET email = EXCLUDED.email
                RETURNING id
                """,
                (email,),
            )
            user_id = cur.fetchone()[0]
    return {"user_id": user_id}


@app.get("/progress/summary")
def summary(user_id: int):
    with psycopg.connect(DB_URL, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT l.id, l.title,
                       lp.attempts, lp.correct, lp.mastered,
                       CASE WHEN lp.attempts>0 THEN lp.correct::float/lp.attempts ELSE 0 END AS accuracy
                FROM lesson_progress lp
                JOIN lesson l ON l.id = lp.lesson_id
                WHERE lp.user_id=%s
                ORDER BY lp.mastered DESC, lp.attempts DESC
            """, (user_id,))
            lessons = [
                {
                    "lesson_id": r[0], "title": r[1],
                    "attempts_total": r[2], "correct_total": r[3],
                    "mastered": r[4], "accuracy": float(r[5])
                }
                for r in cur.fetchall()
            ]
            cur.execute("""
                SELECT topic_code, subtopic_code, attempts, correct,
                       CASE WHEN attempts > 0 THEN correct::float/attempts ELSE 0 END AS accuracy
                FROM topic_stats
                WHERE user_id = %s
                  AND attempts >= 10
                ORDER BY accuracy ASC, attempts DESC
                LIMIT 5
            """, (user_id,))
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


@app.get("/lessons/overview")
def lessons_overview(user_id: int, group: Optional[str] = "grammar"):
    group = (group or "grammar").lower()
    with psycopg.connect(DB_URL, autocommit=True) as conn:
        with conn.cursor() as cur:
            # Detect available columns in lesson table
            cur.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'lesson'
                """
            )
            cols = {r[0] for r in cur.fetchall()}
            topic_col = 'topic_code' if 'topic_code' in cols else ('topic' if 'topic' in cols else None)
            subtopic_select = 'l.subtopic_code' if 'subtopic_code' in cols else 'NULL::text'
            if not topic_col:
                raise HTTPException(500, "lesson_topic_column_not_found")

            where = (
                f"COALESCE(l.{topic_col}, '') ILIKE 'Vocabulary%'"
                if group == "vocabulary"
                else f"COALESCE(l.{topic_col}, '') ILIKE 'Grammar%'"
            )

            sql = f"""
                SELECT l.id, l.title, l.{topic_col} AS topic_value,
                       {subtopic_select} AS subtopic_value,
                       COALESCE(lp.attempts,0) AS attempts,
                       COALESCE(lp.correct,0)  AS correct,
                       COALESCE(lp.mastered,false) AS mastered,
                       CASE WHEN COALESCE(lp.attempts,0)>0
                            THEN COALESCE(lp.correct,0)::float/COALESCE(lp.attempts,0) ELSE 0 END AS accuracy
                FROM lesson l
                LEFT JOIN lesson_progress lp
                  ON lp.user_id = %s AND lp.lesson_id = l.id
                WHERE {where}
                ORDER BY mastered ASC, l.id ASC
            """
            cur.execute(sql, (user_id,))
            rows = cur.fetchall()
            lessons = [
                {
                    "lesson_id": r[0],
                    "title": r[1],
                    "topic": r[2],
                    "subtopic": r[3],
                    "attempts_total": r[4],
                    "correct_total": r[5],
                    "mastered": r[6],
                    "accuracy": float(r[7]),
                }
                for r in rows
            ]
    return {"group": group, "lessons": lessons}


@app.get("/tasks/next")
def next_task(user_id: int, lesson_id: int):
    with psycopg.connect(DB_URL, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT t.id,
                       NULL AS type,
                       t.content AS prompt,
                       t.answer AS answer_schema
                FROM task t
                LEFT JOIN (
                    SELECT task_id, COUNT(*) attempts
                    FROM task_attempt
                    WHERE user_id = %s
                    GROUP BY task_id
                ) a ON a.task_id = t.id
                WHERE t.lesson_id = %s
                ORDER BY COALESCE(a.attempts, 0) ASC, t.id ASC
                LIMIT 1
                """,
                (user_id, lesson_id),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(404, "no_task_for_lesson")
            return {
                "task_id": row[0],
                "type": row[1],
                "prompt": row[2] or {},
                "answer_schema": row[3] or {},
            }


# Static files and root index
STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def root():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"ok": True}


if __name__ == "__main__":
    import os as _os
    import uvicorn as _uvicorn
    _port = int(_os.getenv("PORT", "8000"))
    _uvicorn.run("app.main:app", host="0.0.0.0", port=_port)
