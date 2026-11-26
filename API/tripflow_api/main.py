import asyncio
import json
import logging
import os
import time
from contextlib import AsyncExitStack, asynccontextmanager, closing
from pathlib import Path
from urllib.parse import quote
from typing import Annotated

import httpx
from anyio import CapacityLimiter
from fastapi import Body, BackgroundTasks, Depends, FastAPI, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from fastapi.staticfiles import StaticFiles

from .database import Database
from .portal import ASSETS, Account, configure_portal, data as portal_data, router as portal_router, signed_in
from .schemas import (
    BudgetRequest, Destination, ErrorDetail, ErrorResponse, LegacyTrip, RecommendationsRequest, TaskAccepted,
    TaskRequest, TaskStatus,
)
from .tasks import TaskConflict, TaskStore
from .cities import city_suggestions


API_DIR = Path(__file__).resolve().parents[1]
logger = logging.getLogger("uvicorn.error")
BUILDER_PREFIX = "/portal/data/builder"


async def recover_hotels(tasks: TaskStore) -> None:
    active = set()
    try:
        while True:
            for identity in tasks.runnable_hotels():
                worker = asyncio.create_task(tasks.run(*identity))
                active.add(worker)
                worker.add_done_callback(active.discard)
            await asyncio.sleep(2)
    finally:
        for worker in active:
            worker.cancel()
        await asyncio.gather(*active, return_exceptions=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    destinations_file = API_DIR.parent / "shared" / "data" / "destinations.json"
    destinations = json.loads(destinations_file.read_text(encoding="utf-8"))["destinations"]
    app.state.destinations = destinations
    legacy = {row["id"]: Destination(city=row["city"], countryCode=row["countryCode"], **row["coordinates"])
              for row in destinations}
    app.state.destination_ids = set(legacy)
    on_render = os.environ.get("RENDER") == "true"
    if on_render and not os.environ.get("DATABASE_URL"):
        raise ValueError("Set DATABASE_URL to a persistent PostgreSQL database on Render")
    state_path = Path(os.environ.get("TRIPFLOW_STATE_PATH", API_DIR / ".state" / "tasks.sqlite3"))
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    async with AsyncExitStack() as resources:
        database = resources.enter_context(closing(Database(state_path)))
        provider = await resources.enter_async_context(httpx.AsyncClient(base_url="https://api.deepseek.com", headers=headers))
        external = await resources.enter_async_context(httpx.AsyncClient())
        app.state.external = external
        app.state.geoapify_key = os.environ.get("GEOAPIFY_API_KEY", "").strip()
        app.state.portal = configure_portal(database)
        if on_render and app.state.portal is None:
            raise ValueError("Set the portal owner credentials for the first startup on Render")
        app.state.password_limit = CapacityLimiter(2)
        app.state.portal_attempts = {}
        tasks = TaskStore(database, provider, bool(key), external, legacy)
        app.state.tasks = tasks
        tasks.prune_usage()
        app.state.usage_pruned = int(time.time()) // 86400
        recovery = [asyncio.create_task(tasks.run(*identity)) for identity in tasks.pending()]
        recovery.append(asyncio.create_task(recover_hotels(tasks)))
        try:
            yield
        finally:
            recovery[-1].cancel()
            await asyncio.gather(*recovery, return_exceptions=True)


app = FastAPI(title="TripFlow API", version="1.1.0", lifespan=lifespan, description=(
    "Stage 2: hotel recommendations use verified web sources and return a group price in RUB "
    "for one separate room per traveler and all nights. Attractions and budget are test data. "
    "Follow the relative Location after 202. The hotels category may complete with partial results."
))
app.include_router(portal_router)
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
    builder = path.startswith(BUILDER_PREFIX + "/")
    task_path = path.removeprefix(BUILDER_PREFIX if builder else "/v1")
    tracked = (builder or path.startswith("/v1/")) and (
        (request.method == "POST" and task_path in ("/recommendations", "/budget"))
        or (request.method == "GET" and task_path.startswith("/tasks/"))
    )
    if not tracked:
        return await call_next(request)

    if not builder:
        portal = request.app.state.portal
        key = request.headers.get("X-API-Key")
        request.state.api_client = portal.client_by_key(key) if portal is not None and key else None
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        client = getattr(request.state, "api_client", None)
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
        path = ".".join(str(part) for part in problem["loc"][1:] if part not in ("LocatedTrip", "LegacyTrip")) or "body"
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
    request: Request, response: Response, background: BackgroundTasks, operation: str, body: TaskRequest, client: str,
    *, prefix: str = "/v1",
) -> TaskAccepted:
    if isinstance(body.trip, LegacyTrip) and body.trip.destinationId not in request.app.state.destination_ids:
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
    response.headers["Location"] = prefix + "/tasks/" + quote(body.taskId, safe="")
    response.headers["Retry-After"] = "2"
    return TaskAccepted(taskId=body.taskId)


example_trip = {"destination": {"city": "Киото", "countryCode": "JP", "latitude": 35.01, "longitude": 135.77},
                "startDate": "2027-06-10", "endDate": "2027-06-13",
                "travelers": 2, "budgetRub": 85000, "preferences": "Отель рядом с метро и прогулки по городу"}
recommendation_examples = {
    target: {"summary": label, "value": {
        "taskId": f"{target}-001", "trip": example_trip,
        "targets": target, "count": 2, "maxTotalRub": limit,
        "refinement": refinement, "excludedObjectIds": [],
    }}
    for target, label, limit, refinement in (
        ("hotels", "Отели", 50000, "Можно дальше от центра"),
        ("attractions", "Достопримечательности", 5000, "Музеи и парки"),
    )
}
budget_examples = {"budget": {"summary": "Смета поездки", "value": {
    "taskId": "budget-001", "trip": example_trip,
    "selectedHotel": {
        "objectId": "hotel-boulevard", "price": 16200,
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
    return read_task(taskId, request, response, client)


def read_task(task_id: str, request: Request, response: Response, client: str) -> dict:
    status = request.app.state.tasks.status(client, task_id)
    if status is None:
        raise ApiError(404, task_id, ErrorDetail(code="TASK_NOT_FOUND", message="Unknown task"))
    response.headers["Cache-Control"] = "no-store"
    if status["status"] == "pending":
        response.headers["Retry-After"] = "2"
    return status


async def builder_client(request: Request, account: Annotated[Account, Depends(signed_in)]) -> str:
    request.state.api_client = account["id"]
    return account["id"]


BuilderClient = Annotated[str, Depends(builder_client)]


@portal_data.get("/builder/destinations")
async def builder_destinations(request: Request, _client: BuilderClient) -> list[dict]:
    return request.app.state.destinations


@portal_data.get("/builder/cities")
async def builder_cities(request: Request, _client: BuilderClient, q: Annotated[str, Query(max_length=120)] = "") -> dict:
    return await city_suggestions(request.app.state.external, request.app.state.geoapify_key, q.strip(),
                                  request.app.state.tasks.hotels.remember_place)


@portal_data.post("/builder/recommendations", status_code=202)
async def builder_recommendations(
    request: Request, response: Response, background: BackgroundTasks, body: RecommendationsRequest, client: BuilderClient,
) -> TaskAccepted:
    return accept_task(request, response, background, "recommendations", body, client, prefix=BUILDER_PREFIX)


@portal_data.post("/builder/budget", status_code=202)
async def builder_budget(
    request: Request, response: Response, background: BackgroundTasks, body: BudgetRequest, client: BuilderClient,
) -> TaskAccepted:
    return accept_task(request, response, background, "budget", body, client, prefix=BUILDER_PREFIX)


@portal_data.get("/builder/tasks/{taskId:path}", response_model=TaskStatus)
async def builder_task_status(taskId: str, request: Request, response: Response, client: BuilderClient) -> dict:
    return read_task(taskId, request, response, client)


app.include_router(portal_data)


@app.get("/health", include_in_schema=False)
async def health(request: Request) -> dict:
    request.app.state.tasks.connection.execute("SELECT 1").fetchone()
    return {"status": "ok"}
