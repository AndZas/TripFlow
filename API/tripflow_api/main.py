import asyncio
import json
import logging
import os
import time
from contextlib import asynccontextmanager, closing
from pathlib import Path
from urllib.parse import quote
from typing import Annotated

from anyio import CapacityLimiter
from fastapi import Body, BackgroundTasks, Depends, FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from fastapi.staticfiles import StaticFiles

from .database import Database
from .portal import ASSETS, configure_portal, data as portal_data, router as portal_router
from .schemas import BudgetRequest, ErrorDetail, ErrorResponse, RecommendationsRequest, TaskAccepted, TaskRequest, TaskStatus
from .tasks import TaskConflict, TaskStore


API_DIR = Path(__file__).resolve().parents[1]
logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    destinations_file = API_DIR.parent / "shared" / "data" / "destinations.json"
    destinations = json.loads(destinations_file.read_text(encoding="utf-8"))["destinations"]
    app.state.destination_ids = {destination["id"] for destination in destinations}
    on_render = os.environ.get("RENDER") == "true"
    if on_render and not os.environ.get("DATABASE_URL"):
        raise ValueError("Set DATABASE_URL to a persistent PostgreSQL database on Render")
    state_path = Path(os.environ.get("TRIPFLOW_STATE_PATH", API_DIR / ".state" / "tasks.sqlite3"))
    with closing(Database(state_path)) as database:
        app.state.portal = configure_portal(database)
        if on_render and app.state.portal is None:
            raise ValueError("Set the portal owner credentials for the first startup on Render")
        app.state.password_limit = CapacityLimiter(2)
        app.state.portal_attempts = {}
        tasks = TaskStore(database)
        app.state.tasks = tasks
        tasks.prune_usage()
        app.state.usage_pruned = int(time.time()) // 86400
        recovery = [asyncio.create_task(tasks.run(*identity)) for identity in tasks.pending()]
        try:
            yield
        finally:
            await asyncio.gather(*recovery)


app = FastAPI(title="TripFlow Mock API", version="1.0.0", lifespan=lifespan)
app.include_router(portal_router)
app.include_router(portal_data)
app.mount("/portal/assets", StaticFiles(directory=ASSETS), name="portal-assets")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
error_responses = {
    401: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
}


@app.middleware("http")
async def record_api_usage(request: Request, call_next):
    path = request.url.path
    tracked = (request.method == "POST" and path in ("/v1/recommendations", "/v1/budget")) or (
        request.method == "GET" and path.startswith("/v1/tasks/")
    )
    if not tracked:
        return await call_next(request)

    portal = request.app.state.portal
    key = request.headers.get("X-API-Key")
    client = portal.client_by_key(key) if portal is not None and key else None
    request.state.api_client = client
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        if client is not None:
            tasks = request.app.state.tasks
            try:
                tasks.record_usage(client, request.method, status)
                day = int(time.time()) // 86400
                if app.state.usage_pruned < day:
                    tasks.prune_usage()
                    app.state.usage_pruned = day
            except Exception:
                logger.exception("Could not record API usage")


class ApiError(Exception):
    def __init__(self, status: int, task_id: str | None, detail: ErrorDetail):
        self.status = status
        self.response = ErrorResponse(taskId=task_id, error=detail)


@app.exception_handler(ApiError)
async def api_error_handler(_request: Request, error: ApiError) -> JSONResponse:
    return JSONResponse(error.response.model_dump(exclude_unset=True), status_code=error.status)


@app.exception_handler(RequestValidationError)
async def request_validation_handler(request: Request, error: RequestValidationError) -> JSONResponse:
    task_id = error.body.get("taskId") if isinstance(error.body, dict) else None
    if not isinstance(task_id, str):
        task_id = None
    fields: dict[str, list[str]] = {}
    for problem in error.errors():
        path = ".".join(str(part) for part in problem["loc"][1:]) or "body"
        fields.setdefault(path, []).append(problem["msg"])
    detail = ErrorDetail(code="VALIDATION_ERROR", message="Invalid request", fields=fields)
    return await api_error_handler(request, ApiError(422, task_id, detail))


async def require_api_key(request: Request, key: Annotated[str | None, Depends(api_key_header)]) -> str:
    client = getattr(request.state, "api_client", None)
    if key is not None and client is not None:
        return client
    try:
        body = await request.json()
    except (ValueError, UnicodeError):
        body = None
    task_id = body.get("taskId") if isinstance(body, dict) else None
    detail = ErrorDetail(code="INVALID_API_KEY", message="A valid X-API-Key is required")
    raise ApiError(401, task_id if isinstance(task_id, str) else None, detail)


def accept_task(
    request: Request, response: Response, background: BackgroundTasks, operation: str, body: TaskRequest, client: str
) -> TaskAccepted:
    if body.trip.destinationId not in request.app.state.destination_ids:
        detail = ErrorDetail(
            code="VALIDATION_ERROR",
            message="Invalid request",
            fields={"trip.destinationId": ["Unknown destination"]},
        )
        raise ApiError(422, body.taskId, detail)
    tasks = request.app.state.tasks
    try:
        created = tasks.accept(client, operation, body)
    except TaskConflict:
        detail = ErrorDetail(code="TASK_ID_CONFLICT", message="taskId was already used for a different request")
        raise ApiError(409, body.taskId, detail) from None
    if created:
        background.add_task(tasks.run, client, body.taskId)
    response.headers["Location"] = "/v1/tasks/" + quote(body.taskId, safe="")
    response.headers["Retry-After"] = "2"
    return TaskAccepted(taskId=body.taskId)


example_trip = {"destinationId": "ru-moscow", "startDate": "2027-06-10", "endDate": "2027-06-13",
                "travelers": 2, "budgetRub": 85000, "preferences": "Отель рядом с метро и прогулки по городу"}
recommendation_examples = {
    target: {"summary": label, "value": {
        "taskId": f"{target}-001", "trip": example_trip,
        "targets": {target: {"count": 2, "maxTotalRub": limit}},
    }}
    for target, label, limit in (("hotels", "Отели", 40000), ("attractions", "Достопримечательности", 5000))
}
budget_examples = {"budget": {"summary": "Смета поездки", "value": {
    "taskId": "budget-001", "trip": example_trip,
    "selectedHotel": {
        "objectId": "hotel-boulevard", "price": 16200,
        "tariff": {"name": "Без питания", "includedServices": []},
    },
    "selectedAttractions": [],
}}}


@app.post("/v1/recommendations", status_code=202, responses=error_responses)
async def create_recommendations(
    request: Request, response: Response, background: BackgroundTasks,
    body: Annotated[RecommendationsRequest, Body(openapi_examples=recommendation_examples)],
    client: Annotated[str, Depends(require_api_key)],
) -> TaskAccepted:
    return accept_task(request, response, background, "recommendations", body, client)


@app.post("/v1/budget", status_code=202, responses=error_responses)
async def create_budget(
    request: Request, response: Response, background: BackgroundTasks,
    body: Annotated[BudgetRequest, Body(openapi_examples=budget_examples)],
    client: Annotated[str, Depends(require_api_key)],
) -> TaskAccepted:
    return accept_task(request, response, background, "budget", body, client)

@app.get("/v1/tasks/{taskId:path}", response_model=TaskStatus,
         responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}})
async def task_status(taskId: str, request: Request, response: Response,
                      client: Annotated[str, Depends(require_api_key)]) -> dict:
    status = request.app.state.tasks.status(client, taskId)
    if status is None:
        raise ApiError(404, taskId, ErrorDetail(code="TASK_NOT_FOUND", message="Unknown task"))
    response.headers["Cache-Control"] = "no-store"
    if status["status"] == "pending":
        response.headers["Retry-After"] = "2"
    return status


@app.get("/health", include_in_schema=False)
async def health(request: Request) -> dict:
    request.app.state.tasks.connection.execute("SELECT 1").fetchone()
    return {"status": "ok"}
