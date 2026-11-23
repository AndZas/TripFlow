import asyncio
import hashlib
import json
import re
import time
from uuid import uuid4

import httpx

from .database import Database
from .preference_model import (
    INPUT_LIMIT, MAX_ATTEMPTS, MODEL, PROMPT_VERSION, STAGE_SECONDS, USAGE_FIELDS,
    AnalysisError, parse_conditions, provider_content, provider_reply, provider_usage, request_body,
)


EMPTY = {"conditions": [], "changes": []}
WINDOW_SECONDS = 7 * 86400
CORE_USAGE = ("inputTokens", "outputTokens", "totalTokens")


def encode(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def elapsed_ms(start: float) -> int:
    return round((time.monotonic() - start) * 1000)


class PreferenceAnalysis:
    def __init__(self, db: Database, client: httpx.AsyncClient, configured: bool):
        self.db = db
        self.client = client
        self.configured = configured
        self.slots = asyncio.Semaphore(3)
        with db.transaction():
            db.execute("""
                CREATE TABLE IF NOT EXISTS preference_tasks (
                    client_id TEXT NOT NULL, task_id TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
                    duration_ms INTEGER, error TEXT,
                    PRIMARY KEY (client_id, task_id),
                    FOREIGN KEY (client_id, task_id) REFERENCES tasks(client_id, task_id)
                )
            """)
            db.execute("""
                CREATE TABLE IF NOT EXISTS preference_runs (
                    client_id TEXT NOT NULL, id TEXT NOT NULL, cache_key TEXT, task_id TEXT NOT NULL,
                    stage TEXT NOT NULL, model TEXT NOT NULL, version TEXT NOT NULL,
                    started_at BIGINT NOT NULL, expires_at BIGINT NOT NULL, status TEXT NOT NULL,
                    result TEXT, error TEXT,
                    PRIMARY KEY (client_id, id)
                )
            """)
            db.execute("CREATE UNIQUE INDEX IF NOT EXISTS preference_cache ON preference_runs(client_id, cache_key)")
            db.execute("""
                CREATE TABLE IF NOT EXISTS preference_links (
                    client_id TEXT NOT NULL, task_id TEXT NOT NULL, stage TEXT NOT NULL,
                    run_id TEXT NOT NULL, source TEXT NOT NULL,
                    PRIMARY KEY (client_id, task_id, stage),
                    FOREIGN KEY (client_id, task_id) REFERENCES preference_tasks(client_id, task_id),
                    FOREIGN KEY (client_id, run_id) REFERENCES preference_runs(client_id, id)
                )
            """)
            db.execute("""
                CREATE TABLE IF NOT EXISTS preference_attempts (
                    client_id TEXT NOT NULL, run_id TEXT NOT NULL, number INTEGER NOT NULL,
                    started_at BIGINT NOT NULL, duration_ms INTEGER, usage TEXT, error TEXT, model TEXT,
                    PRIMARY KEY (client_id, run_id, number),
                    FOREIGN KEY (client_id, run_id) REFERENCES preference_runs(client_id, id)
                )
            """)
            db.execute("CREATE INDEX IF NOT EXISTS preference_attempt_dates ON preference_attempts(client_id, started_at)")

    def register(self, client_id: str, task_id: str) -> None:
        self.db.execute("INSERT INTO preference_tasks (client_id, task_id) VALUES (?, ?)", (client_id, task_id))

    def finish_task(self, client_id: str, task_id: str, status: str, duration: int, error: str | None) -> None:
        self.db.execute("""
            UPDATE preference_tasks SET status = ?, duration_ms = ?, error = ?
            WHERE client_id = ? AND task_id = ? AND status = 'pending'
        """, (status, duration, error, client_id, task_id))

    def linked(self, client_id: str, task_id: str) -> list[dict]:
        return self.db.records("""
            SELECT r.*, l.source FROM preference_links l JOIN preference_runs r
              ON r.client_id = l.client_id AND r.id = l.run_id
            WHERE l.client_id = ? AND l.task_id = ? ORDER BY l.stage
        """, (client_id, task_id))

    def expire(self, client_id: str, run_id: str, now: int) -> None:
        expired = self.db.execute("""
            UPDATE preference_runs SET status = 'failed', error = 'interrupted', cache_key = NULL
            WHERE client_id = ? AND id = ? AND status = 'pending' AND expires_at <= ?
        """, (client_id, run_id, now))
        if expired.rowcount:
            self.db.execute("""
                UPDATE preference_attempts SET error = 'interrupted'
                WHERE client_id = ? AND run_id = ? AND duration_ms IS NULL
            """, (client_id, run_id))

    def claim(self, client_id: str, task_id: str, stage: str, data: dict, base_id: str | None) -> tuple[str, bool]:
        text = data["preferences"] if stage == "preferences" else data["refinement"]
        cache_key = hashlib.sha256(encode([MODEL, PROMPT_VERSION, stage, base_id, data.get("category"), text]).encode()).hexdigest()
        if not text:
            status, error, result = "empty", None, encode(EMPTY)
        elif len(text) > INPUT_LIMIT:
            status, error, result = "failed", "input_too_long", None
        elif not self.configured:
            status, error, result = "unconfigured", "missing_key", None
        else:
            status, error, result = "pending", None, None

        identity = (client_id, task_id, stage)
        with self.db.transaction():
            # Serialize duplicate workers for a task on PostgreSQL. SQLite already holds the write lock.
            self.db.execute("SELECT task_id FROM preference_tasks WHERE client_id = ? AND task_id = ?"
                            + (" FOR UPDATE" if self.db.postgres else ""), identity[:2]).fetchone()
            link = self.db.execute("SELECT run_id FROM preference_links WHERE client_id = ? AND task_id = ? AND stage = ?",
                                   identity).fetchone()
            if link is not None:
                return link[0], False
            while True:
                now = int(time.time())
                incumbents = self.db.records("SELECT id, status, expires_at FROM preference_runs WHERE client_id = ? AND cache_key = ?",
                                             (client_id, cache_key))
                if incumbents:
                    incumbent = incumbents[0]
                    if incumbent["status"] == "pending" and incumbent["expires_at"] <= now:
                        self.expire(client_id, incumbent["id"], now)
                        continue
                    run_id = incumbent["id"]
                    source = "empty" if incumbent["status"] == "empty" else "reused"
                    break
                run_id = uuid4().hex
                inserted = self.db.execute("""
                    INSERT INTO preference_runs (client_id, id, cache_key, task_id, stage, model, version,
                        started_at, expires_at, status, result, error)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT DO NOTHING
                """, (client_id, run_id, cache_key if status in ("pending", "empty") else None, task_id, stage,
                      MODEL, PROMPT_VERSION, now, now + STAGE_SECONDS + 5, status, result, error))
                if inserted.rowcount:
                    source = {"pending": "call", "empty": "empty"}.get(status, "unavailable")
                    break
            self.db.execute("INSERT INTO preference_links (client_id, task_id, stage, run_id, source) VALUES (?, ?, ?, ?, ?)",
                            (*identity, run_id, source))
        return run_id, source == "call"

    async def attempt(self, client_id: str, run_id: str, number: int, data: dict, correction: str | None) -> dict:
        body = request_body(data, correction)
        identity = (client_id, run_id, number)
        self.db.execute("INSERT INTO preference_attempts (client_id, run_id, number, started_at) VALUES (?, ?, ?, ?)",
                        (*identity, int(time.time())))
        started = time.monotonic()
        usage, error, model = {}, None, None
        try:
            status, reply = await provider_reply(self.client, body)
            usage = provider_usage(reply)
            reported = reply.get("model")
            if isinstance(reported, str) and re.fullmatch(r"[a-zA-Z0-9._-]{1,100}", reported):
                model = reported
            return parse_conditions(provider_content(status, reply), data)
        except AnalysisError as failure:
            error = failure.code
            raise
        except asyncio.CancelledError:
            error = "interrupted"
            raise
        finally:
            self.db.execute("""
                UPDATE preference_attempts SET duration_ms = ?, usage = ?, error = ?, model = ?
                WHERE client_id = ? AND run_id = ? AND number = ?
            """, (elapsed_ms(started), encode(usage) if usage else None, error, model, *identity))

    async def compute(self, client_id: str, run_id: str, data: dict) -> None:
        result, error = None, None
        try:
            async with asyncio.timeout(STAGE_SECONDS), self.slots:
                for number in range(1, MAX_ATTEMPTS + 1):
                    try:
                        result = await self.attempt(client_id, run_id, number, data, error)
                    except AnalysisError as failure:
                        error = failure.code
                        if not failure.retryable:
                            break
                    else:
                        error = None
                        break
        except TimeoutError:
            error = "timeout"
        except asyncio.CancelledError:
            error = "interrupted"
            raise
        finally:
            status = "succeeded" if result is not None else "failed"
            self.db.execute("""
                UPDATE preference_runs SET status = ?, result = ?, error = ?,
                    cache_key = CASE WHEN ? = 'succeeded' THEN cache_key ELSE NULL END
                WHERE client_id = ? AND id = ? AND status = 'pending'
            """, (status, encode(result) if result is not None else None,
                  error or ("internal" if result is None else None), status,
                  client_id, run_id))

    async def stage(self, client_id: str, task_id: str, stage: str, data: dict, base_id: str | None = None) -> dict:
        run_id, execute = self.claim(client_id, task_id, stage, data, base_id)
        if execute:
            await self.compute(client_id, run_id, data)
        while True:
            run = self.db.records("SELECT id, status, result, error, expires_at FROM preference_runs WHERE client_id = ? AND id = ?",
                                  (client_id, run_id))[0]
            if run["status"] != "pending":
                return run
            now = int(time.time())
            if now >= run["expires_at"]:
                with self.db.transaction():
                    self.expire(client_id, run_id, now)
            else:
                await asyncio.sleep(0.2)

    async def run(self, client_id: str, task_id: str, body: dict) -> None:
        identity = (client_id, task_id)
        row = self.db.execute("SELECT status FROM preference_tasks WHERE client_id = ? AND task_id = ?", identity).fetchone()
        if row != ("pending",):
            return
        started = time.monotonic()
        preferences = (body["trip"].get("preferences") or "").strip()
        refinement = (body.get("refinement") or "").strip()
        base = await self.stage(*identity, "preferences", {"preferences": preferences})
        final = base
        if refinement and base["status"] in ("empty", "succeeded"):
            category = body["targets"]
            conditions = json.loads(base["result"])["conditions"]
            final = await self.stage(*identity, "refinement", {
                "preferences": preferences, "refinement": refinement, "category": category,
                "base": [{"index": i, **item} for i, item in enumerate(conditions) if item["scope"] == category],
            }, base["id"])
        self.finish_task(*identity, final["status"], elapsed_ms(started), final["error"])

    def details(self, client_id: str, task_id: str, body: dict) -> dict:
        task = self.db.records("SELECT status, duration_ms, error FROM preference_tasks WHERE client_id = ? AND task_id = ?",
                               (client_id, task_id))
        if not task:
            return {"status": "historical", "stages": []}
        stages = []
        for run in self.linked(client_id, task_id):
            attempts = self.db.records("""
                SELECT number, started_at, duration_ms, usage, error, model FROM preference_attempts
                WHERE client_id = ? AND run_id = ? ORDER BY number
            """, (client_id, run["id"]))
            for attempt in attempts:
                attempt["usage"] = json.loads(attempt["usage"]) if attempt["usage"] else None
            stages.append({
                "id": run["id"], "stage": run["stage"], "status": run["status"], "source": run["source"],
                "model": run["model"], "version": run["version"], "started_at": run["started_at"],
                "error": run["error"], "initiatorTaskId": run["task_id"] if attempts else None,
                "result": json.loads(run["result"]) if run["result"] else None, "attempts": attempts,
            })
        return {**task[0], "preferences": body["trip"].get("preferences"), "refinement": body.get("refinement"),
                "category": body["targets"], "stages": stages}

    def summary(self, client_id: str) -> dict:
        end = int(time.time())
        start = end - WINDOW_SECONDS
        counts = self.db.execute("""
            SELECT p.status, COUNT(*) FROM preference_tasks p JOIN tasks t
              ON t.client_id = p.client_id AND t.task_id = p.task_id
            WHERE p.client_id = ? AND t.created_at BETWEEN ? AND ? GROUP BY p.status
        """, (client_id, start, end)).fetchall()
        reused = self.db.execute("""
            SELECT COUNT(*) FROM preference_links l
            JOIN tasks t ON t.client_id = l.client_id AND t.task_id = l.task_id
            JOIN preference_runs r ON r.client_id = l.client_id AND r.id = l.run_id
            WHERE l.client_id = ? AND l.source = 'reused' AND r.status = 'succeeded' AND t.created_at BETWEEN ? AND ?
        """, (client_id, start, end)).fetchone()[0]
        attempts = self.db.execute("""
            SELECT duration_ms, usage FROM preference_attempts WHERE client_id = ? AND started_at BETWEEN ? AND ?
        """, (client_id, start, end)).fetchall()
        totals = dict.fromkeys(USAGE_FIELDS)
        known = dict.fromkeys(USAGE_FIELDS, 0)
        durations = []
        incomplete = 0
        for duration, usage in attempts:
            if duration is not None:
                durations.append(duration)
            reported = json.loads(usage) if usage else {}
            for name, amount in reported.items():
                totals[name] = (totals[name] or 0) + amount
                known[name] += 1
            incomplete += not all(field in reported for field in CORE_USAGE)
        return {
            "start": start, "end": end, "tasks": dict(counts), "attempts": len(attempts), "reused": reused,
            "usage": totals, "usageObservations": known, "incompleteUsage": incomplete,
            "averageMs": round(sum(durations) / len(durations)) if durations else None, "durationObservations": len(durations),
        }
