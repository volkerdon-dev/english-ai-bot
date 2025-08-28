import os
from typing import Optional, List, Dict, Tuple
from fastapi import FastAPI, HTTPException, Request, Body
from fastapi.responses import JSONResponse, FileResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import logging
from pydantic import BaseModel, Field
import psycopg
from psycopg.types.json import Json
from psycopg.rows import dict_row
from datetime import datetime, timezone
import re
import hmac
import hashlib
from urllib.parse import parse_qsl
import json
import httpx

# --- Compatibility for tests using httpx.ASGITransport with sync Client ---
try:
    from httpx import ASGITransport as _ASGITransport
    if not hasattr(_ASGITransport, "__enter__"):
        def _asgi_enter(self):
            return self
        def _asgi_exit(self, exc_type, exc, tb):
            return False
        setattr(_ASGITransport, "__enter__", _asgi_enter)
        setattr(_ASGITransport, "__exit__", _asgi_exit)
    # Provide sync handle_request if missing (wraps async handler)
    if not hasattr(_ASGITransport, "handle_request") and hasattr(_ASGITransport, "handle_async_request"):
        def _handle_request(self, request):
            import asyncio as _asyncio
            import httpx as _httpx
            async def _runner():
                resp = await self.handle_async_request(request)
                try:
                    await resp.aread()
                except Exception:
                    pass
                # Create a new sync Response with in-memory bytes content
                return _httpx.Response(
                    status_code=resp.status_code,
                    headers=resp.headers,
                    content=resp.content,
                    request=request,
                    extensions=resp.extensions,
                )
            return _asyncio.run(_runner())
        setattr(_ASGITransport, "handle_request", _handle_request)
except Exception:
    pass

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
    user_id: Optional[int] = None
    task_id: int
    lesson_id: Optional[int] = None
    is_correct: bool
    score: Optional[float] = None
    response: dict = Field(default_factory=dict)
    error_tags: List[str] = Field(default_factory=list)


class AuthTgIn(BaseModel):
    tg_user_id: Optional[int] = None
    init_data: Optional[str] = None


logger = logging.getLogger("app")


def _is_pro(user_row: dict) -> bool:
    if not user_row:
        return False
    if user_row.get("plan") == "pro":
        return True
    pro_until = user_row.get("pro_until")
    if isinstance(pro_until, str):
        try:
            pro_until = datetime.fromisoformat(pro_until)
        except Exception:
            pro_until = None
    return bool(pro_until and pro_until > datetime.now(timezone.utc))


def _has_entitlement(user_row: dict, key: str) -> bool:
    if _is_pro(user_row):
        return True
    ent = user_row.get("entitlements") or {}
    try:
        return bool(ent.get(key) is True)
    except AttributeError:
        return False


def _get_user_row(conn, user_id: int):
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT id, plan, pro_until, entitlements FROM app_user WHERE id=%s",
            (user_id,),
        )
        return cur.fetchone()


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
            # Resolve lesson_id for the task
            cur.execute("SELECT lesson_id FROM task WHERE id=%s", (a.task_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(400, "task_id not found")
            lesson_id = row[0]

            # Guest mode: no user_id provided -> do not persist, return minimal progress stub
            if a.user_id is None:
                return {
                    "attemptId": None,
                    "lessonId": lesson_id,
                    "progress": {
                        "attempts_total": 1,
                        "correct_total": 1 if a.is_correct else 0,
                        "mastered": False,
                        "accuracy": 1.0 if a.is_correct else 0.0,
                    },
                }

            # Persist attempt for authenticated users
            cur.execute(
                """
                INSERT INTO task_attempt (user_id, task_id, response, is_correct)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (a.user_id, a.task_id, Json(a.response), a.is_correct),
            )
            attempt_id = cur.fetchone()[0]

            # Read progress aggregate
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


@app.post("/auth/tg")
def auth_tg(payload: AuthTgIn):
    # Verify Telegram initData HMAC if provided/required
    bot_token = os.getenv("BOT_TOKEN", "")
    tg_user_id: Optional[int] = None

    if bot_token:
        if not payload.init_data:
            raise HTTPException(status_code=401, detail="init_data_required")
        secret_key = hashlib.sha256(bot_token.encode()).digest()
        # Parse init_data and verify hash
        items = dict(parse_qsl(payload.init_data, keep_blank_values=True))
        recv_hash = items.pop("hash", None)
        data_check_string = "\n".join(f"{k}={items[k]}" for k in sorted(items.keys()))
        calc_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        if not (recv_hash and hmac.compare_digest(recv_hash, calc_hash)):
            raise HTTPException(status_code=401, detail="invalid_signature")
        # Extract user id from 'user' JSON if present; otherwise fallback to explicit tg_user_id
        user_json = items.get("user")
        if user_json:
            try:
                user_obj = json.loads(user_json)
                tg_user_id = int(user_obj.get("id"))
            except Exception:
                tg_user_id = None
    # Fallback (e.g., local dev without BOT_TOKEN)
    if tg_user_id is None:
        tg_user_id = payload.tg_user_id or None
    if not tg_user_id:
        raise HTTPException(status_code=400, detail="tg_user_id_missing")

    email = f"tg-{tg_user_id}@tg.local"
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
        user = _get_user_row(conn, user_id) or {}

    return {
        "userId": user_id,
        "plan": user.get("plan", "free"),
        "proUntil": user.get("pro_until"),
        "entitlements": user.get("entitlements") or {},
    }


@app.get("/progress/summary")
def summary(user_id: int):
    with psycopg.connect(DB_URL, autocommit=True) as conn:
        # Entitlement gate
        user = _get_user_row(conn, user_id)
        if not _has_entitlement(user, "progress_summary"):
            raise HTTPException(status_code=402, detail="progress_summary_required")
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


# Admin plan toggle endpoint
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")


@app.post("/admin/users/{uid}/plan")
def set_plan(uid: int, request: Request, plan: str = Body(..., embed=True), days: Optional[int] = Body(None, embed=True)):
    token = request.headers.get("X-Admin-Token")
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="forbidden")
    with psycopg.connect(DB_URL, autocommit=True) as conn:
        with conn.cursor() as cur:
            if plan == "pro" and days:
                # Note: days is sanitized as int in interval
                days_int = int(days)
                cur.execute(
                    f"UPDATE app_user SET plan=%s, pro_until=NOW() + INTERVAL '{days_int} days' WHERE id=%s",
                    (plan, uid),
                )
            else:
                cur.execute("UPDATE app_user SET plan=%s, pro_until=NULL WHERE id=%s", (plan, uid))
    return {"ok": True}


@app.get("/lessons/overview")
def lessons_overview(
    user_id: Optional[int] = None,
    group: Optional[str] = "grammar",
    section: Optional[str] = None,
    subsection: Optional[str] = None,
    unit: Optional[str] = None,
):
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

            # Build parameterized ILIKE conditions to avoid raw % tokens in SQL
            if group == "vocabulary":
                patterns = [
                    "Vocabulary%",
                    "Vocab%",
                    "🧠%",
                ]
            else:
                patterns = [
                    "Grammar%",
                    "📚%",
                    "📌%",
                    "🧱%",
                    "🛠%",
                    "🚫%",
                ]

            topic_full = f"COALESCE(l.{topic_col}, '')"
            conds = [f"{topic_full} ILIKE %s" for _ in patterns]
            where = "(" + " OR ".join(conds) + ")"

            # Optional hierarchical filters: section / subsection / unit
            filters: List[str] = []
            params_filters: List[str] = []
            parts: List[str] = []
            if section:
                parts.append(section.strip())
            if subsection:
                parts.append(subsection.strip())
            if unit:
                parts.append(unit.strip())
            if parts:
                like_pattern = " / ".join([f"%{p}%" for p in parts]) + "%"
                filters.append(f"{topic_full} ILIKE %s")
                params_filters.append(like_pattern)

            select_base = f"""
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
            """

            extra_where = (" AND " + " AND ".join(filters)) if filters else ""
            sql_filtered = f"{select_base}\n                WHERE {where}{extra_where}\n                ORDER BY mastered ASC, l.id ASC"
            params = [user_id, *patterns, *params_filters]
            cur.execute(sql_filtered, params)
            rows = cur.fetchall()
            # Optional fallback: if no rows matched, return all lessons to avoid empty UI
            if not rows:
                sql_all = f"{select_base}\n                ORDER BY mastered ASC, l.id ASC"
                cur.execute(sql_all, (user_id,))
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
def next_task(lesson_id: int, user_id: Optional[int] = None):
    with psycopg.connect(DB_URL, autocommit=True) as conn:
        with conn.cursor() as cur:
            if user_id is not None:
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
            else:
                cur.execute(
                    """
                    SELECT t.id,
                           NULL AS type,
                           t.content AS prompt,
                           t.answer AS answer_schema
                    FROM task t
                    WHERE t.lesson_id = %s
                    ORDER BY t.id ASC
                    LIMIT 1
                    """,
                    (lesson_id,),
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


# Public lesson details (theory/metadata)
@app.get("/lesson/{lesson_id}")
def get_lesson(lesson_id: int):
    with psycopg.connect(DB_URL, autocommit=True) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT id, title, topic, metadata FROM lesson WHERE id=%s",
                (lesson_id,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(404, "lesson_not_found")
            # Expose theory if present inside metadata
            theory = None
            try:
                meta = row.get("metadata") or {}
                theory = meta.get("theory")
            except Exception:
                theory = None
            return {
                "lesson_id": row["id"],
                "title": row["title"],
                "topic": row.get("topic"),
                "theory": theory,
                "metadata": row.get("metadata") or {},
            }


# Static files and root index
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Mount legacy assets (root-level HTML/CSS/JS) under /legacy to avoid path clashes
LEGACY_DIR = BASE_DIR
if os.path.isdir(LEGACY_DIR):
    app.mount("/legacy", StaticFiles(directory=LEGACY_DIR), name="legacy")


@app.get("/")
def root():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"ok": True}


CLASSIC_GRAMMAR_URL = os.getenv("CLASSIC_GRAMMAR_URL")


# Friendly redirect for Grammar section. If CLASSIC_GRAMMAR_URL is set, use it; otherwise serve bundled legacy page
@app.get("/grammar")
def grammar_legacy_redirect():
    target = CLASSIC_GRAMMAR_URL or "/static/legacy/grammar.html"
    return RedirectResponse(url=target)


@app.get("/vocabulary")
def vocabulary_legacy_redirect():
    return RedirectResponse(url="/static/legacy/vocabulary.html")


@app.get("/legacy/grammar.html", include_in_schema=False)
def legacy_grammar_html():
    if CLASSIC_GRAMMAR_URL:
        return RedirectResponse(CLASSIC_GRAMMAR_URL, status_code=302)
    # Serve new static legacy page if available
    new_path = os.path.join(STATIC_DIR, "legacy", "grammar.html")
    if os.path.exists(new_path):
        return FileResponse(new_path)
    # Fallback to old root-level legacy file
    legacy_path = os.path.join(LEGACY_DIR, "grammar.html")
    if os.path.exists(legacy_path):
        return FileResponse(legacy_path)
    # As a last resort, redirect to /grammar (which will handle routing)
    return RedirectResponse(url="/grammar")


# ---- Catalog Tree Endpoint ----

def _slugify(value: str) -> str:
    if not value:
        return ""
    value = value.strip().lower()
    # replace emojis and non-word with hyphen
    value = re.sub(r"[\W_]+", "-", value, flags=re.UNICODE)
    value = re.sub(r"-+", "-", value).strip("-")
    return value


def _split_hierarchy(topic_full: str) -> Tuple[str, Optional[str], Optional[str]]:
    if not topic_full:
        return ("", None, None)
    parts = [p.strip() for p in topic_full.split(" / ")]
    if len(parts) == 1:
        return (parts[0], None, None)
    if len(parts) == 2:
        return (parts[0], parts[1], None)
    return (parts[0], parts[1], parts[2])


@app.get("/catalog/tree")
def catalog_tree(group: str):
    group = (group or "").lower()
    if group not in ("grammar", "vocabulary"):
        raise HTTPException(status_code=400, detail="invalid_group")

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
            if not topic_col:
                raise HTTPException(500, "lesson_topic_column_not_found")

            if group == "vocabulary":
                patterns = [
                    "Vocabulary%",
                    "Vocab%",
                    "🧠%",
                ]
            else:
                patterns = [
                    "Grammar%",
                    "📚%",
                    "📌%",
                    "🧱%",
                    "🛠%",
                    "🚫%",
                ]

            topic_full = f"COALESCE(l.{topic_col}, '')"
            conds = [f"{topic_full} ILIKE %s" for _ in patterns]
            where = "(" + " OR ".join(conds) + ")"

            sql = f"""
                SELECT l.id AS lesson_id, {topic_full} AS topic_full, l.title
                FROM lesson l
                WHERE {where}
                ORDER BY l.id
            """
            cur.execute(sql, patterns)
            lessons = cur.fetchall()

            # Build nested dict structure
            tree: Dict[str, dict] = {}
            unit_to_lessons: Dict[str, List[int]] = {}

            for lesson_id, topic_value, lesson_title in lessons:
                sec, sub, uni = _split_hierarchy(topic_value)
                if not sec:
                    # skip orphaned
                    continue
                sec_code = _slugify(sec)
                if sec_code not in tree:
                    tree[sec_code] = {"code": sec_code, "title": sec, "subsections": {}}
                if sub:
                    sub_code = _slugify(sub)
                else:
                    sub_code = "_default"
                    sub = "General"
                subsections = tree[sec_code]["subsections"]
                if sub_code not in subsections:
                    subsections[sub_code] = {"code": sub_code, "title": sub, "units": {}}
                if uni:
                    unit_title = uni
                else:
                    unit_title = lesson_title or f"Lesson {lesson_id}"
                unit_code = _slugify(unit_title)
                units = subsections[sub_code]["units"]
                if unit_code not in units:
                    units[unit_code] = {"code": unit_code, "title": unit_title, "lessonIds": []}
                units[unit_code]["lessonIds"].append(lesson_id)
                unit_to_lessons.setdefault(unit_code, []).append(lesson_id)

            # Determine hasPractice per unit in one query
            all_lesson_ids: List[int] = []
            for ids in unit_to_lessons.values():
                all_lesson_ids.extend(ids)
            practice_set: set = set()
            if all_lesson_ids:
                cur.execute(
                    "SELECT DISTINCT lesson_id FROM task WHERE lesson_id = ANY(%s)",
                    (all_lesson_ids,),
                )
                practice_set = {r[0] for r in cur.fetchall()}

            # Normalize to list and annotate hasPractice
            sections_out: List[dict] = []
            for sec_code, sec_obj in tree.items():
                subsections_out: List[dict] = []
                for sub_code, sub_obj in sec_obj["subsections"].items():
                    units_out: List[dict] = []
                    for unit_code, unit_obj in sub_obj["units"].items():
                        lesson_ids = unit_obj["lessonIds"]
                        has_practice = any(lid in practice_set for lid in lesson_ids)
                        units_out.append({
                            "code": unit_code,
                            "title": unit_obj["title"],
                            "lessonIds": lesson_ids,
                            "hasPractice": has_practice,
                        })
                    subsections_out.append({
                        "code": sub_obj["code"],
                        "title": sub_obj["title"],
                        "units": units_out,
                    })
                sections_out.append({
                    "code": sec_obj["code"],
                    "title": sec_obj["title"],
                    "subsections": subsections_out,
                })

    return {"group": group, "sections": sections_out}


# ---- Billing: Telegram Payments ----

@app.post("/billing/create_invoice_link")
def create_invoice_link():
    bot_token = os.getenv("BOT_TOKEN", "")
    price_cents = int(os.getenv("PRO_PRICE_CENTS", "0") or 0)
    title = os.getenv("PRO_TITLE", "EngTrain Pro")
    desc = os.getenv("PRO_DESC", "One year of EngTrain Pro access")
    provider_token = os.getenv("PRO_PROVIDER_TOKEN", "")
    currency = os.getenv("PRO_CURRENCY", "USD")

    if not bot_token or not provider_token or price_cents <= 0:
        raise HTTPException(status_code=500, detail="billing_not_configured")

    api_url = f"https://api.telegram.org/bot{bot_token}/createInvoiceLink"
    payload = {
        "title": title,
        "description": desc,
        "payload": "engtrain_pro_1y",
        "provider_token": provider_token,
        "currency": currency,
        "prices": [{"label": "Pro", "amount": price_cents}],
    }
    try:
        with httpx.Client(timeout=10.0) as client:
            res = client.post(api_url, json=payload)
            data = res.json()
            if not data.get("ok"):
                logger.error("createInvoiceLink failed: %s", data)
                raise HTTPException(status_code=502, detail="telegram_api_error")
            return {"url": data["result"]}
    except httpx.RequestError:
        raise HTTPException(status_code=502, detail="telegram_unreachable")


@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    bot_token = os.getenv("BOT_TOKEN", "")
    if not bot_token:
        # allow in dev
        return {"ok": True}
    body = await request.json()
    # Detect successful payment in update
    message = body.get("message") or {}
    sp = message.get("successful_payment")
    if sp:
        from_user = message.get("from") or {}
        tg_id = from_user.get("id")
        if tg_id:
            email = f"tg-{tg_id}@tg.local"
            with psycopg.connect(DB_URL, autocommit=True) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE app_user
                        SET plan='pro', pro_until=NOW() + INTERVAL '365 days'
                        WHERE email=%s
                        """,
                        (email,),
                    )
            return {"ok": True}
    return {"ok": True}


if __name__ == "__main__":
    import os as _os
    import uvicorn as _uvicorn
    _port = int(_os.getenv("PORT", "8000"))
    _uvicorn.run("app.main:app", host="0.0.0.0", port=_port)
