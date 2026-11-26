import asyncio
import json
import logging
import os
import time
from uuid import uuid4

import httpx

from . import mock_results
from .database import Database
from .hotel_catalog import HotelCatalog
from .hotel_enrichment import HotelEnrichment
from .hotel_tools import BudgetStop, HotelTools, JOB_SECONDS, SLOTS, SearchInterrupted, initialize_attempts, search_profile
from .hotels import HotelSearch, result_for
from .preferences import PreferenceAnalysis
from .schemas import BudgetRequest, Destination, LocatedTrip, RecommendationsRequest, TaskRequest


logger = logging.getLogger("uvicorn.error")
DEMO_CLIENT_ID = "demo"
HOUR_SECONDS = 3600
USAGE_DAYS = 7
LEASE_SECONDS = 18

TASKS_SCHEMA = """
    CREATE TABLE IF NOT EXISTS tasks (
        client_id TEXT NOT NULL,
        task_id TEXT NOT NULL,
        operation TEXT NOT NULL,
        payload TEXT NOT NULL,
        result TEXT,
        finished INTEGER NOT NULL DEFAULT 0,
        created_at INTEGER NOT NULL,
        PRIMARY KEY (client_id, task_id)
    )
"""


class TaskConflict(Exception):
    pass


class TaskStore:
    def __init__(self, connection: Database, provider: httpx.AsyncClient, configured: bool,
                 external: httpx.AsyncClient, destinations: dict[str, Destination]):
        self.connection = connection
        self.provider = provider
        self.configured = configured
        self.external = external
        self.destinations = destinations
        self.hotel_profile = search_profile()
        self.hotel_enrichment = os.getenv("HOTEL_ENRICHMENT", "on").strip().lower() != "off"
        self.geoapify_key = os.getenv("GEOAPIFY_API_KEY", "").strip()
        with connection.transaction():
            columns = connection.columns("tasks")
            if columns and "client_id" not in columns:
                connection.execute("ALTER TABLE tasks RENAME TO tasks_before_portal")
                connection.execute(TASKS_SCHEMA)
                connection.execute("""
                    INSERT INTO tasks (client_id, task_id, operation, payload, result, finished, created_at)
                    SELECT ?, task_id, operation, payload, result, finished, 0
                    FROM tasks_before_portal
                """, (DEMO_CLIENT_ID,))
                connection.execute("DROP TABLE tasks_before_portal")
            else:
                connection.execute(TASKS_SCHEMA)
            columns = connection.columns("tasks")
            for name, declaration in (
                ("handler_version", "INTEGER NOT NULL DEFAULT 1"), ("hotel_started", "BIGINT"),
                ("hotel_lease", "TEXT"), ("hotel_expires_at", "BIGINT"), ("hotel_job", "INTEGER NOT NULL DEFAULT 0"),
            ):
                if name not in columns:
                    connection.execute(f"ALTER TABLE tasks ADD COLUMN {name} {declaration}")
            connection.execute("CREATE INDEX IF NOT EXISTS tasks_by_client_date ON tasks(client_id, created_at DESC)")
            connection.execute("""
                CREATE INDEX IF NOT EXISTS hotel_jobs_pending ON tasks(created_at)
                WHERE hotel_job = 1 AND result IS NULL
            """)
            connection.execute("""
                CREATE TABLE IF NOT EXISTS hotel_worker_slots (
                    slot INTEGER PRIMARY KEY, lease TEXT, expires_at BIGINT NOT NULL DEFAULT 0
                )
            """)
            for slot in range(SLOTS):
                connection.execute("INSERT INTO hotel_worker_slots (slot) VALUES (?) ON CONFLICT DO NOTHING", (slot,))
            initialize_attempts(connection)
            self.hotels = HotelCatalog(connection)

            connection.execute("""
                CREATE TABLE IF NOT EXISTS api_usage_hours (
                    client_id TEXT NOT NULL, hour INTEGER NOT NULL,
                    submissions INTEGER NOT NULL, polls INTEGER NOT NULL, errors INTEGER NOT NULL,
                    PRIMARY KEY (client_id, hour)
                )
            """)
        self.preferences = PreferenceAnalysis(connection, provider, configured)

    def record_usage(self, client_id: str, method: str, status_code: int) -> None:
        hour = int(time.time()) // HOUR_SECONDS
        self.connection.execute(
            """INSERT INTO api_usage_hours (client_id, hour, submissions, polls, errors) VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(client_id, hour) DO UPDATE SET
                 submissions = api_usage_hours.submissions + excluded.submissions,
                 polls = api_usage_hours.polls + excluded.polls,
                 errors = api_usage_hours.errors + excluded.errors""",
            (client_id, hour, int(method == "POST"), int(method == "GET"), int(status_code >= 400)),
        )

    def usage(self, client_id: str) -> dict:
        hour = int(time.time()) // HOUR_SECONDS
        rows = self.connection.execute(
            """SELECT hour, submissions, polls, errors FROM api_usage_hours
               WHERE client_id = ? AND hour BETWEEN ? AND ? ORDER BY hour""",
            (client_id, hour - USAGE_DAYS * 24 + 1, hour),
        ).fetchall()
        return {
            "last24h": sum(posts + polls for bucket, posts, polls, _ in rows if bucket >= hour - 23),
            "submissions": sum(posts for _, posts, _, _ in rows),
            "polls": sum(polls for _, _, polls, _ in rows),
            "errors": sum(errors for _, _, _, errors in rows),
            "peakPerHour": max((posts + polls for _, posts, polls, _ in rows), default=0),
            "lastRequestHour": rows[-1][0] * HOUR_SECONDS if rows else None,
        }

    def prune_usage(self) -> None:
        hour = int(time.time()) // HOUR_SECONDS
        self.connection.execute("DELETE FROM api_usage_hours WHERE hour < ?", (hour - USAGE_DAYS * 24,))

    def accept(self, client_id: str, operation: str, request: TaskRequest) -> bool:
        body = request.model_dump(mode="json")
        if body.get("targetHotelTotalRub") is None:
            body.pop("targetHotelTotalRub", None)
        payload = json.dumps(body, sort_keys=True, ensure_ascii=False)
        with self.connection.transaction():
            inserted = self.connection.execute(
                "INSERT INTO tasks (client_id, task_id, operation, payload, created_at, handler_version, hotel_job) "
                "VALUES (?, ?, ?, ?, ?, 2, ?) "
                "ON CONFLICT(client_id, task_id) DO NOTHING",
                (client_id, request.taskId, operation, payload, int(time.time()),
                 int(isinstance(request, RecommendationsRequest) and request.targets == "hotels")),
            )
            if inserted.rowcount:
                if operation == "recommendations":
                    self.preferences.register(client_id, request.taskId)
                return True
            previous = self.connection.execute(
                "SELECT operation, payload FROM tasks WHERE client_id = ? AND task_id = ?",
                (client_id, request.taskId),
            ).fetchone()
            previous_body = json.loads(previous[1])
            if previous_body.get("targetHotelTotalRub") is None:
                previous_body.pop("targetHotelTotalRub", None)
            previous_body.pop("callbackUrl", None)  # Older stored requests.
            if previous[0] != operation or previous_body != json.loads(payload):
                raise TaskConflict
        return False

    def pending(self) -> list[tuple[str, str]]:
        return self.connection.execute("SELECT client_id, task_id FROM tasks WHERE result IS NULL").fetchall()

    def load(self, client_id: str, task_id: str) -> tuple[str, str, str | None]:
        return self.connection.execute(
            "SELECT operation, payload, result FROM tasks WHERE client_id = ? AND task_id = ?", (client_id, task_id)
        ).fetchone()

    def status(self, client_id: str, task_id: str) -> dict | None:
        row = self.connection.execute(
            "SELECT result FROM tasks WHERE client_id = ? AND task_id = ?", (client_id, task_id)
        ).fetchone()
        if row is None:
            return None
        if row[0] is None:
            return {"taskId": task_id, "status": "pending", "result": None}
        result = json.loads(row[0])
        for hotel in result.get("results", {}).get("hotels", {}).get("items", []):
            hotel.pop("tariff", None)  # Results saved before the contract change.
        return {"taskId": task_id, "status": "completed", "result": result}

    async def run(self, client_id: str, task_id: str) -> None:
        identity = (client_id, task_id)
        row = self.connection.execute(
            "SELECT operation, payload, result, handler_version FROM tasks WHERE client_id = ? AND task_id = ?", identity
        ).fetchone()
        if row is None:
            return
        operation, payload, result, version = row
        if result is None:
            body = json.loads(payload)
            body.pop("callbackUrl", None)
            if version >= 2 and operation == "recommendations" and body["targets"] == "hotels":
                await self.run_hotels(identity, body)
                return
            if operation == "recommendations":
                started = time.monotonic()
                try:
                    await self.preferences.run(client_id, task_id, body)
                except Exception:
                    logger.error("Preference analysis failed internally")
                    try:
                        self.preferences.finish_task(client_id, task_id, "failed",
                                                     round((time.monotonic() - started) * 1000), "internal")
                    except Exception:
                        logger.error("Could not save the preference analysis status")
            result = json.dumps(build_result(task_id, operation, body, historical=version < 2), ensure_ascii=False)
            self.connection.execute(
                "UPDATE tasks SET result = ?, finished = 1 WHERE client_id = ? AND task_id = ? AND result IS NULL",
                (result, client_id, task_id),
            )

    def runnable_hotels(self):
        return self.connection.execute("""
            SELECT client_id, task_id FROM tasks WHERE hotel_job = 1 AND result IS NULL
              AND (hotel_expires_at IS NULL OR hotel_expires_at <= ?)
              AND created_at <= ?
            ORDER BY created_at LIMIT ?
        """, (int(time.time()), int(time.time()) - 2, SLOTS)).fetchall()

    def claim_hotels(self, identity, lease):
        db = self.connection
        now = int(time.time())
        with db.transaction():
            slot = db.execute("""
                SELECT slot FROM hotel_worker_slots WHERE expires_at <= ? ORDER BY slot LIMIT 1
            """ + (" FOR UPDATE SKIP LOCKED" if db.postgres else ""), (now,)).fetchone()
            if slot is None:
                return None
            expiry = now + LEASE_SECONDS
            row = db.execute("""
                UPDATE tasks SET hotel_lease = ?, hotel_expires_at = ?, hotel_started = COALESCE(hotel_started, ?)
                WHERE client_id = ? AND task_id = ? AND result IS NULL
                  AND (hotel_expires_at IS NULL OR hotel_expires_at <= ?)
                RETURNING hotel_started
            """, (lease, expiry, int(time.time() * 1000), *identity, now)).fetchone()
            if row is None:
                return None
            db.execute("UPDATE hotel_worker_slots SET lease = ?, expires_at = ? WHERE slot = ?", (lease, expiry, slot[0]))
            return row[0]

    async def renew_hotel_lease(self, identity, lease, worker):
        while True:
            await asyncio.sleep(LEASE_SECONDS / 3)
            now = int(time.time())
            expiry = now + LEASE_SECONDS
            with self.connection.transaction():
                slot = self.connection.execute(
                    "UPDATE hotel_worker_slots SET expires_at = ? WHERE lease = ? AND expires_at > ?",
                    (expiry, lease, now),
                )
                task = self.connection.execute("""
                    UPDATE tasks SET hotel_expires_at = ? WHERE client_id = ? AND task_id = ?
                    AND hotel_lease = ? AND hotel_expires_at > ?
                """, (expiry, *identity, lease, now))
            if not slot.rowcount or not task.rowcount:
                worker.cancel()
                return

    async def run_hotels(self, identity, body):
        lease = uuid4().hex
        started = self.claim_hotels(identity, lease)
        if started is None:
            return
        started = started / 1000 if started >= 10**12 else started
        heartbeat = asyncio.create_task(self.renew_hotel_lease(identity, lease, asyncio.current_task()))
        search, error, exhausted = None, None, False
        request = RecommendationsRequest.model_validate(body)
        destination = (request.trip.destination if isinstance(request.trip, LocatedTrip)
                       else self.destinations.get(request.trip.destinationId))
        try:
            try:
                async with asyncio.timeout(started + JOB_SECONDS - time.time()) as deadline:
                    conditions = []
                    if request.trip.startDate != request.trip.endDate:
                        await self.preferences.run(*identity, body)
                        conditions = self.preferences.hotel_conditions(*identity, refined=request.refinement is not None)
                        if conditions is None:
                            raise SearchInterrupted("preferences")
                    else:
                        self.preferences.finish_task(*identity, "empty", 0, None)
                    if destination is None:
                        raise SearchInterrupted("destination")
                    tools = HotelTools(self.connection, self.provider, self.external, identity, lease, deadline.when(), self.hotel_profile)
                    search = HotelSearch(self.hotels, tools, self.configured, destination, request, conditions, self.geoapify_key)
                    error, exhausted = await search.run()
            except TimeoutError:
                error = "timeout"
                if search:
                    search.record_stop(BudgetStop(search.tools.stage, "time", JOB_SECONDS * 1000, JOB_SECONDS * 1000, 0))
                self.preferences.finish_task(*identity, "failed", 0, error)
            except SearchInterrupted as failure:
                error = failure.code
                if search:
                    search.record_stop(failure)
            except Exception:
                logger.exception("Hotel search failed internally")
                error = "internal"
                self.preferences.finish_task(*identity, "failed", 0, error)
            if search and search.matches and self.hotel_enrichment:
                remaining = min(18, search.tools.deadline - time.monotonic())
                if remaining > 0:
                    try:
                        async with asyncio.timeout(remaining):
                            await HotelEnrichment(search).run()
                    except (TimeoutError, SearchInterrupted):
                        pass
            result = result_for(identity[1], request.count, search.matches if search else [], error, exhausted,
                                search.stop_message(error) if search else None)
            diagnostics = search.diagnostics(error) if search else {"error": error, "hotels": [], "catalogLookups": 0,
                                                                     "catalogMatches": 0}
            diagnostics["elapsedMs"] = max(0, round((time.time() - started) * 1000))
            with self.connection.transaction():
                saved = self.connection.execute("""
                    UPDATE tasks SET result = ?, finished = 1, hotel_lease = NULL, hotel_expires_at = NULL
                    WHERE client_id = ? AND task_id = ? AND hotel_lease = ? AND hotel_expires_at > ? AND result IS NULL
                """, (json.dumps(result, ensure_ascii=False), *identity, lease, int(time.time())))
                if saved.rowcount:
                    self.connection.execute("""
                        INSERT INTO hotel_diagnostics (client_id, task_id, initial_catalog, outcome) VALUES (?, ?, '{}', ?)
                        ON CONFLICT(client_id, task_id) DO UPDATE SET outcome = excluded.outcome
                    """, (*identity, json.dumps(diagnostics, ensure_ascii=False)))
        finally:
            heartbeat.cancel()
            await asyncio.gather(heartbeat, return_exceptions=True)
            with self.connection.transaction():
                self.connection.execute("UPDATE hotel_worker_slots SET lease = NULL, expires_at = 0 WHERE lease = ?", (lease,))
                self.connection.execute("""
                    UPDATE tasks SET hotel_lease = NULL, hotel_expires_at = NULL
                    WHERE client_id = ? AND task_id = ? AND hotel_lease = ?
                """, (*identity, lease))

    def summary(self, client_id: str) -> dict:
        total, pending = self.connection.execute(
            "SELECT COUNT(*), COUNT(*) - COUNT(result) FROM tasks WHERE client_id = ?", (client_id,)
        ).fetchone()
        return {"total": total, "pending": pending}

    def recent(self, client_id: str) -> list[dict]:
        rows = self.connection.execute(
            "SELECT task_id, operation, created_at, CASE WHEN result IS NULL THEN 'pending' ELSE 'completed' END FROM tasks WHERE client_id = ? "
            "ORDER BY created_at DESC, task_id DESC LIMIT 30",
            (client_id,),
        )
        return [
            {"taskId": task_id, "operation": operation, "createdAt": created_at, "status": status}
            for task_id, operation, created_at, status in rows
        ]


def build_result(task_id: str, operation: str, body: dict, *, historical: bool) -> dict:
    if operation == "recommendations":
        targets = body["targets"]
        # Recover jobs accepted before the request was limited to one category.
        if isinstance(targets, dict):
            requests = {
                kind: {"taskId": task_id, "trip": body["trip"], "targets": kind,
                       "refinement": None, "excludedObjectIds": None, **settings}
                for kind, settings in targets.items()
            }
        else:
            requests = {targets: body}
        return {
            "taskId": task_id,
            "event": "recommendations.finished",
            "results": {kind: build_recommendation_result(request, historical=historical)
                        for kind, request in requests.items()},
        }

    try:
        hotel = body.get("selectedHotel")
        if isinstance(hotel, dict):
            hotel.pop("tariff", None)
        return mock_results.budget(BudgetRequest.model_validate(body))
    except Exception:
        logger.exception("Budget task %r failed", task_id)
        return {
            "taskId": task_id,
            "event": "budget.finished",
            "status": "failed",
            "expenses": None,
            "error": {"code": "BUDGET_ESTIMATE_FAILED", "message": "Mock budget failed"},
        }


def build_recommendation_result(body: dict, *, historical: bool) -> dict:
    try:
        return mock_results.recommendations(RecommendationsRequest.model_validate(body), historical=historical)
    except Exception:
        logger.exception("Recommendations task %r failed", body["taskId"])
        return {
            "status": "failed",
            "items": [],
            "hasMore": None,
            "error": {"code": "RECOMMENDATIONS_FAILED", "message": "Mock search failed"},
        }
