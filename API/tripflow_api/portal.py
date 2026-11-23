import json
import os
import re
import time
from pathlib import Path
from typing import Annotated, Literal

from anyio import to_thread
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel, Field

from .database import Database
from .portal_store import (
    SESSION_SECONDS,
    PortalStore,
    RegistrationError,
    password_hasher,
    valid_password,
)


ASSETS = Path(__file__).with_name("portal_assets")
SESSION_COOKIE = "tripflow_portal"
EMAIL = r"[^\s@]+@[^\s@]+\.[^\s@]+"
AUTH_LIMIT = 12
AUTH_WINDOW_SECONDS = 60
Account = dict


def configure_portal(database: Database) -> PortalStore | None:
    email = os.environ.get("TRIPFLOW_PORTAL_ADMIN_EMAIL", "").strip().lower()
    password = os.environ.get("TRIPFLOW_PORTAL_ADMIN_PASSWORD", "")
    store = PortalStore(database)
    if not store.one("SELECT id FROM portal_accounts WHERE role = 'owner'", ()) and email:
        if len(email) > 254 or not re.fullmatch(EMAIL, email):
            raise ValueError("Set TRIPFLOW_PORTAL_ADMIN_EMAIL to your email")
    return store if store.bootstrap_owner(email, password) else None


class Credentials(BaseModel):
    email: Annotated[str, Field(min_length=3, max_length=254)]
    password: Annotated[str, Field(min_length=1, max_length=128)]


class AccountUpdate(BaseModel):
    action: Literal["approve", "reject", "disable", "promote", "demote"]


async def protect_portal_write(request: Request, response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"
    if request.method == "POST" and request.headers.get("X-Portal-Request") != "1":
        raise HTTPException(403, "Откройте кабинет и повторите действие.")


router = APIRouter(include_in_schema=False)
data = APIRouter(prefix="/portal/data", include_in_schema=False, dependencies=[Depends(protect_portal_write)])


@router.get("/")
async def open_portal() -> RedirectResponse:
    return RedirectResponse("/portal", status_code=302)


@router.get("/portal")
async def portal_page() -> FileResponse:
    return FileResponse(ASSETS / "index.html", headers={
        "Cache-Control": "no-cache",
        "Content-Security-Policy": (
            "default-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        ),
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "no-referrer",
    })


async def portal_store(request: Request) -> PortalStore:
    store = request.app.state.portal
    if store is None:
        raise HTTPException(503, "Кабинет ещё не настроен.")
    return store


async def signed_in(
    request: Request, store: Annotated[PortalStore, Depends(portal_store)]
) -> Account:
    token = request.cookies.get(SESSION_COOKIE, "")
    account = store.find_session(token) if token else None
    if account is None:
        raise HTTPException(401, "Войдите в кабинет.")
    return account


async def admin_only(account: Annotated[Account, Depends(signed_in)]) -> Account:
    if account["role"] not in ("owner", "admin"):
        raise HTTPException(403, "Это действие доступно администратору.")
    return account


async def limit_auth_attempts(request: Request) -> None:
    now = time.monotonic()
    limits = request.app.state.portal_attempts
    for source, (until, _) in list(limits.items()):
        if until <= now:
            del limits[source]
    source = request.client.host if request.client else "unknown"
    until, attempts = limits.get(source, (now + AUTH_WINDOW_SECONDS, 0))
    if attempts >= AUTH_LIMIT:
        raise HTTPException(429, "Слишком много попыток. Повторите через минуту.")
    limits[source] = (until, attempts + 1)


def set_session(request: Request, response: Response, store: PortalStore, account_id: str) -> None:
    response.set_cookie(
        SESSION_COOKIE, store.start_session(account_id), max_age=SESSION_SECONDS,
        path="/portal", secure=request.url.scheme == "https" or os.environ.get("RENDER") == "true", httponly=True, samesite="strict",
    )


def describe_account(account: Account) -> dict:
    return {
        "id": account["id"],
        "email": account["email"],
        "role": account["role"],
        "active": bool(account["active"]),
        "status": account["access_status"],
        "ownerReview": bool(account["owner_review"]),
        "createdAt": account["created_at"],
        "keys": {
            "api": {"hint": account["api_hint"], "issuedAt": account["api_issued"]},
        },
    }


@data.get("/session")
async def get_session(request: Request) -> dict:
    store = request.app.state.portal
    if not store:
        return {"enabled": False, "account": None}
    token = request.cookies.get(SESSION_COOKIE, "")
    account = store.find_session(token) if token else None
    return {"enabled": True, "account": describe_account(account) if account else None}


@data.post("/login", dependencies=[Depends(limit_auth_attempts)])
async def login(
    request: Request, response: Response, body: Credentials,
    store: Annotated[PortalStore, Depends(portal_store)],
) -> dict:
    account = store.find_email(body.email.strip().lower())
    password_hash = account["password_hash"] if account else store.dummy_password_hash
    valid = await to_thread.run_sync(valid_password, password_hash, body.password, limiter=request.app.state.password_limit)
    if valid and account is not None:
        account = store.find_email(account["email"])
    if not valid or account is None or account["password_hash"] != password_hash:
        raise HTTPException(401, "Неверный email или пароль.")
    if not account["active"]:
        messages = {"pending": "Заявка ожидает решения администратора.", "rejected": "Заявка отклонена администратором."}
        raise HTTPException(403, messages.get(account["access_status"], "Доступ отключён. Подайте новую заявку с прежними email и паролем."))
    set_session(request, response, store, account["id"])
    return {"account": describe_account(account)}


@data.post("/register", dependencies=[Depends(limit_auth_attempts)])
async def register(
    request: Request, body: Credentials,
    store: Annotated[PortalStore, Depends(portal_store)],
) -> dict:
    email = body.email.strip().lower()
    if not re.fullmatch(EMAIL, email):
        raise HTTPException(422, "Введите корректный email.")
    account = store.find_email(email)
    limiter = request.app.state.password_limit
    if account:
        password_hash = account["password_hash"]
        valid = await to_thread.run_sync(valid_password, password_hash, body.password, limiter=limiter)
        if not valid or not store.reapply(account["id"], password_hash):
            raise HTTPException(409, "Для этого email уже есть аккаунт. Войдите, чтобы проверить статус.")
    else:
        if len(body.password) < 12:
            raise HTTPException(422, "Для нового аккаунта нужен пароль от 12 символов.")
        password_hash = await to_thread.run_sync(password_hasher.hash, body.password, limiter=limiter)
        try:
            store.register(email, password_hash)
        except RegistrationError as exc:
            raise HTTPException(409, str(exc)) from exc
    return {"status": "pending"}


@data.post("/logout")
async def logout(
    request: Request, response: Response, store: Annotated[PortalStore, Depends(portal_store)]
) -> dict:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        store.end_session(token)
    response.delete_cookie(SESSION_COOKIE, path="/portal", secure=request.url.scheme == "https" or os.environ.get("RENDER") == "true", httponly=True, samesite="strict")
    return {"ok": True}


@data.post("/keys/api/issue")
async def issue_key(
    account: Annotated[Account, Depends(signed_in)],
    store: Annotated[PortalStore, Depends(portal_store)],
) -> dict:
    return {"key": store.issue_key(account["id"])}


@data.post("/keys/api/revoke")
async def revoke_key(
    account: Annotated[Account, Depends(signed_in)],
    store: Annotated[PortalStore, Depends(portal_store)],
) -> dict:
    store.revoke_key(account["id"])
    return {"ok": True}


@data.get("/activity")
async def activity(request: Request, account: Annotated[Account, Depends(signed_in)]) -> dict:
    store = request.app.state.tasks
    client_id = account["id"]
    return {"tasks": store.recent(client_id), "summary": store.summary(client_id),
            "preferences": store.preferences.summary(client_id)}


@data.get("/preferences/tasks/{task_id:path}")
async def task_preferences(task_id: str, request: Request, account: Annotated[Account, Depends(signed_in)]) -> dict:
    store = request.app.state.tasks
    row = store.load(account["id"], task_id)
    if row is None or row[0] != "recommendations":
        raise HTTPException(404, "Задача подбора не найдена.")
    return store.preferences.details(account["id"], task_id, json.loads(row[1]))


Admin = Annotated[Account, Depends(admin_only)]
Store = Annotated[PortalStore, Depends(portal_store)]


def managed_account(account_id: str, actor: Account, store: PortalStore) -> Account:
    target = store.find_account(account_id)
    if target is None or (actor["role"] != "owner" and target["role"] != "developer"):
        raise HTTPException(404, "Аккаунт не найден.")
    return target


@data.get("/admin/accounts")
async def list_accounts(actor: Admin, store: Store) -> dict:
    return {"accounts": [describe_account(account) for account in store.accounts(actor["role"])]}


@data.post("/admin/accounts/{account_id}")
async def update_account(account_id: str, body: AccountUpdate, actor: Admin, store: Store) -> dict:
    action = body.action
    target = managed_account(account_id, actor, store)
    owner = actor["role"] == "owner"
    if target["role"] == "owner" or (not owner and (target["owner_review"] or action not in ("approve", "reject"))):
        raise HTTPException(403, "Это действие доступно только владельцу.")
    if action == "disable":
        changed = store.disable(account_id)
    elif action in ("promote", "demote"):
        changed = store.change_role(account_id, action)
    else:
        changed = store.decide(account_id, action, actor["role"])
    if not changed:
        raise HTTPException(409, "Статус или роль аккаунта уже изменились. Обновите список.")
    return {"ok": True}


@data.get("/admin/accounts/{account_id}/activity")
async def account_activity(account_id: str, request: Request, actor: Admin, store: Store) -> dict:
    managed_account(account_id, actor, store)
    tasks = request.app.state.tasks
    return {"tasks": tasks.recent(account_id), "summary": tasks.summary(account_id),
            "usage": tasks.usage(account_id)}
