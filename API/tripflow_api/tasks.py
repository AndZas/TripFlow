import json
import logging
from .database import Database
import time
from . import mock_results
from .schemas import BudgetRequest, RecommendationsRequest, TaskRequest


logger = logging.getLogger("uvicorn.error")
DEMO_CLIENT_ID = "demo"
HOUR_SECONDS = 3600
USAGE_DAYS = 7

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
    def __init__(self, connection: Database):
        self.connection = connection
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
            connection.execute("CREATE INDEX IF NOT EXISTS tasks_by_client_date ON tasks(client_id, created_at DESC)")

            connection.execute("""
                CREATE TABLE IF NOT EXISTS api_usage_hours (
                    client_id TEXT NOT NULL, hour INTEGER NOT NULL,
                    submissions INTEGER NOT NULL, polls INTEGER NOT NULL, errors INTEGER NOT NULL,
                    PRIMARY KEY (client_id, hour)
                )
            """)

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
        payload = json.dumps(request.model_dump(mode="json"), sort_keys=True, ensure_ascii=False)
        with self.connection.transaction():
            inserted = self.connection.execute(
                "INSERT INTO tasks (client_id, task_id, operation, payload, created_at) VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(client_id, task_id) DO NOTHING",
                (client_id, request.taskId, operation, payload, int(time.time())),
            )
            if inserted.rowcount:
                return True
            previous = self.connection.execute(
                "SELECT operation, payload FROM tasks WHERE client_id = ? AND task_id = ?",
                (client_id, request.taskId),
            ).fetchone()
            previous_body = json.loads(previous[1])
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
        return {"taskId": task_id, "status": "completed" if row[0] else "pending",
                "result": json.loads(row[0]) if row[0] else None}

    async def run(self, client_id: str, task_id: str) -> None:
        operation, payload, result = self.load(client_id, task_id)
        if result is None:
            body = json.loads(payload)
            body.pop("callbackUrl", None)
            result = json.dumps(build_result(task_id, operation, json.dumps(body)), ensure_ascii=False)
            self.connection.execute(
                "UPDATE tasks SET result = ?, finished = 1 WHERE client_id = ? AND task_id = ?",
                (result, client_id, task_id),
            )

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


def build_result(task_id: str, operation: str, payload: str) -> dict:
    try:
        if operation == "budget":
            return mock_results.budget(BudgetRequest.model_validate_json(payload))
        return mock_results.recommendations(RecommendationsRequest.model_validate_json(payload))
    except Exception:
        logger.exception("Mock task %r failed", task_id)
        if operation == "budget":
            return {
                "taskId": task_id,
                "event": "budget.finished",
                "status": "failed",
                "expenses": None,
                "error": {"code": "BUDGET_ESTIMATE_FAILED", "message": "Mock budget failed"},
            }
        return {
            "taskId": task_id,
            "event": "recommendations.finished",
            "results": {
                kind: {
                    "status": "failed",
                    "items": [],
                    "hasMore": None,
                    "error": {"code": "RECOMMENDATIONS_FAILED", "message": "Mock search failed"},
                }
                for kind in json.loads(payload)["targets"]
            },
        }
