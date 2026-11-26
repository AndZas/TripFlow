import asyncio
import hashlib
import json
import os
import time
from xml.etree import ElementTree

import httpx

from .preference_model import AnalysisError, MODEL, provider_content, provider_reply, provider_usage
from .preferences import encode


# Counts are physical requests, including retries and unfinished attempts.
LIMITS = {"search": 7, "fetch": 5, "flash": 6, "fx": 2, "geocode": 1, "places": 1, "russhotels": 2,
          "enrich_search": 2, "enrich_fetch": 6}
EXTENDED = {"search": 10, "fetch": 8, "flash": 10}
EXTRA_FLASH_BYTES = 240_000
EXTRA_FLASH_OUTPUT = 30_000
SEARCH_RESULTS = 6
MAX_FLASH_BYTES = 150_000
MAX_FLASH_OUTPUT = 18_000
JOB_SECONDS = 210
SLOTS = 3
FX_URL = "https://www.cbr.ru/scripts/XML_daily.asp"
REUSE_SECONDS = 30 * 60
BAD_EXTRACTION = frozenset(("flash_truncated", "flash_response", "invalid_response"))


def search_profile():
    profile = os.getenv("HOTEL_SEARCH_PROFILE", "B").strip().upper()
    if profile not in ("A", "B"):
        raise ValueError("HOTEL_SEARCH_PROFILE must be A or B")
    return profile


class SearchInterrupted(Exception):
    def __init__(self, code: str, retryable: bool = False, usage: dict | None = None):
        self.code = code
        self.retryable = retryable
        self.usage = usage
        self.finish_reason = None


class BudgetStop(SearchInterrupted):
    def __init__(self, stage, unit, used, limit, requested):
        super().__init__("token_limit" if unit in ("input_bytes", "output_reserve") else "timeout" if unit == "time"
                         else stage + "_limit")
        self.detail = {"stage": stage, "unit": unit, "used": used, "limit": limit, "requested": requested}


def initialize_attempts(db):
    db.execute("""
        CREATE TABLE IF NOT EXISTS hotel_attempts (
            client_id TEXT NOT NULL, task_id TEXT NOT NULL, attempt INTEGER NOT NULL,
            kind TEXT NOT NULL, step TEXT NOT NULL, started_at BIGINT NOT NULL, duration_ms INTEGER,
            request_bytes INTEGER NOT NULL, output_reserved INTEGER NOT NULL,
            response TEXT, usage TEXT, error TEXT, billable INTEGER,
            PRIMARY KEY (client_id, task_id, attempt)
        )
    """)
    if "finish_reason" not in db.columns("hotel_attempts"):
        db.execute("ALTER TABLE hotel_attempts ADD COLUMN finish_reason TEXT")
    db.execute("""
        CREATE TABLE IF NOT EXISTS hotel_task_profile (
            client_id TEXT NOT NULL, task_id TEXT NOT NULL, profile TEXT NOT NULL,
            PRIMARY KEY (client_id, task_id)
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS hotel_fx_cache (
            source TEXT PRIMARY KEY, received_at BIGINT NOT NULL, document TEXT NOT NULL
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS hotel_search_work (
            client_id TEXT NOT NULL, fingerprint TEXT NOT NULL, task_id TEXT NOT NULL,
            PRIMARY KEY (client_id, fingerprint)
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS hotel_step_cache (
            client_id TEXT NOT NULL, fingerprint TEXT NOT NULL, step TEXT NOT NULL,
            saved_at BIGINT NOT NULL, response TEXT NOT NULL, failure TEXT,
            PRIMARY KEY (client_id, fingerprint, step)
        )
    """)
    if "failure" not in db.columns("hotel_step_cache"):
        db.execute("ALTER TABLE hotel_step_cache ADD COLUMN failure TEXT")


class HotelTools:
    def __init__(self, db, provider, external, identity, lease, deadline=None, profile="A"):
        self.db = db
        self.provider = provider
        self.external = external
        self.identity = identity
        self.lease = lease
        self.deadline = deadline
        self.work = None
        self.reused = {}
        self.stage = "plan"
        self.profile = profile
        self.promising = False
        self.used_extension = False

    async def begin_work(self, fingerprint):
        while True:
            with self.db.transaction():
                self.require_lease()
                client, task = self.identity
                key = (client, fingerprint)
                self.db.execute("""
                    INSERT INTO hotel_search_work VALUES (?, ?, ?) ON CONFLICT DO NOTHING
                """, (*key, task))
                owner = self.db.execute("""
                    SELECT task_id FROM hotel_search_work WHERE client_id = ? AND fingerprint = ?
                """ + (" FOR UPDATE" if self.db.postgres else ""), key).fetchone()[0]
                active = owner != task and self.db.execute("""
                    SELECT 1 FROM tasks WHERE client_id = ? AND task_id = ? AND result IS NULL AND hotel_expires_at > ?
                """, (client, owner, int(time.time()))).fetchone()
                if not active:
                    self.db.execute("""
                        UPDATE hotel_search_work SET task_id = ? WHERE client_id = ? AND fingerprint = ?
                    """, (task, *key))
                    self.db.execute("""
                        DELETE FROM hotel_step_cache WHERE client_id = ? AND fingerprint = ? AND saved_at < ?
                    """, (*key, int(time.time()) - REUSE_SECONDS))
                    self.db.execute("INSERT INTO hotel_task_profile VALUES (?, ?, ?) ON CONFLICT DO NOTHING",
                                    (*self.identity, self.profile))
                    self.profile = self.db.execute(
                        "SELECT profile FROM hotel_task_profile WHERE client_id = ? AND task_id = ?",
                        self.identity).fetchone()[0]
                    self.work = key
                    self.used_extension = self.profile == "B" and any(
                        value["used"] > value["limit"] for value in self.budget().values())
                    return
            await asyncio.sleep(0.2)

    def attempts(self):
        return self.db.execute("""
            SELECT attempt, kind, request_bytes, output_reserved, step, error FROM hotel_attempts
            WHERE client_id = ? AND task_id = ? ORDER BY attempt
        """, self.identity).fetchall()

    @staticmethod
    def step_key(kind, body):
        return hashlib.sha256(encode([kind, body]).encode("utf-8")).hexdigest()

    def cached(self, kind, step):
        own = self.db.execute("""
            SELECT response, NULL FROM hotel_attempts WHERE client_id = ? AND task_id = ? AND step = ?
                AND response IS NOT NULL
        """, (*self.identity, step)).fetchone()
        if own:
            return own, False
        if self.work and kind != "fx":
            shared = self.db.execute("""
                SELECT response, failure FROM hotel_step_cache
                WHERE client_id = ? AND fingerprint = ? AND step = ? AND saved_at >= ?
            """, (*self.work, step, int(time.time()) - REUSE_SECONDS)).fetchone()
            return shared, bool(shared)
        return None, False

    def budget(self, attempts=None, *, report=False):
        attempts = self.attempts() if attempts is None else attempts
        extended = self.profile == "B" and (self.promising or report)
        limits = {**LIMITS, **EXTENDED} if extended else LIMITS
        totals = {kind: {"used": sum(row[1] == kind for row in attempts), "limit": limit}
                  for kind, limit in limits.items()}
        totals["input_bytes"] = {"used": sum(row[2] for row in attempts if row[1] == "flash"), "limit": EXTRA_FLASH_BYTES if extended else MAX_FLASH_BYTES}
        totals["output_reserve"] = {"used": sum(row[3] for row in attempts if row[1] == "flash"), "limit": EXTRA_FLASH_OUTPUT if extended else MAX_FLASH_OUTPUT}
        if self.deadline is not None:
            remaining = max(0, int((self.deadline - time.monotonic()) * 1000))
            totals["time"] = {"used": max(0, JOB_SECONDS * 1000 - remaining), "limit": JOB_SECONDS * 1000}
        return totals

    def require_budget(self, kind, body, attempts=None, *, base=False):
        totals = self.budget(attempts)
        if base:
            totals[kind]["limit"] = LIMITS[kind]
            totals["input_bytes"]["limit"] = MAX_FLASH_BYTES
            totals["output_reserve"]["limit"] = MAX_FLASH_OUTPUT
        units = {kind: 1}
        if kind == "flash":
            units.update(input_bytes=len(encode(body).encode("utf-8")), output_reserve=body["max_tokens"])
        if "time" in totals:
            units["time"] = 1
        for unit, requested in units.items():
            used, limit = totals[unit]["used"], totals[unit]["limit"]
            if used + requested > limit:
                raise BudgetStop(kind, "calls" if unit == kind else unit, used, limit, requested)

    def check(self, kind, body):
        if not self.cached(kind, self.step_key(kind, body))[0]:
            self.require_budget(kind, body)

    def require_lease(self):
        still_owned = self.db.execute("""
            SELECT 1 FROM tasks WHERE client_id = ? AND task_id = ?
            AND hotel_lease = ? AND hotel_expires_at > ? AND result IS NULL
        """ + (" FOR UPDATE" if self.db.postgres else ""), (*self.identity, self.lease, int(time.time()))).fetchone()
        if not still_owned:
            raise asyncio.CancelledError

    async def step(self, kind, body, operation):
        self.stage = kind
        step = self.step_key(kind, body)
        previous, shared = self.cached(kind, step)
        if previous:
            if shared:
                self.reused[step] = kind
            if previous[1]:
                raise SearchInterrupted(previous[1])
            return json.loads(previous[0])

        size = len(encode(body).encode())
        output = body.get("max_tokens", 0)
        while True:
            with self.db.transaction():
                self.require_lease()
                attempts = self.attempts()
                earlier = [row for row in attempts if row[4] == step]
                if len(earlier) >= 2 or (earlier and earlier[-1][5] in
                        (BAD_EXTRACTION | {"authorization", "balance", "source_blocked", "source_unavailable", "provider_rejected"})):
                    raise SearchInterrupted(earlier[-1][5] or "interrupted")
                self.require_budget(kind, body, attempts)
                if self.profile == "B" and self.promising and not self.used_extension:
                    try:
                        self.require_budget(kind, body, attempts, base=True)
                    except BudgetStop:
                        self.used_extension = True
                number = attempts[-1][0] + 1 if attempts else 1
                self.db.execute("""
                    INSERT INTO hotel_attempts (client_id, task_id, attempt, kind, step, started_at,
                        request_bytes, output_reserved) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (*self.identity, number, kind, step, int(time.time()), size, output))
            started = time.monotonic()
            result, usage, error, billable, finish_reason = None, None, None, None, None
            try:
                result, usage, billable, *metadata = await operation(body)
                finish_reason = metadata[0] if metadata else None
                return result
            except SearchInterrupted as failure:
                error, usage, finish_reason = failure.code, failure.usage, failure.finish_reason
                if not failure.retryable or earlier:
                    raise
            except asyncio.CancelledError:
                error = "interrupted"
                raise
            finally:
                with self.db.transaction():
                    self.require_lease()
                    self.db.execute("""
                        UPDATE hotel_attempts SET duration_ms = ?, response = ?, usage = ?, error = ?, billable = ?, finish_reason = ?
                        WHERE client_id = ? AND task_id = ? AND attempt = ?
                    """, (round((time.monotonic() - started) * 1000), encode(result) if result is not None else None,
                          encode(usage) if usage else None, error, billable, finish_reason, *self.identity, number))
                    if self.work and kind != "fx" and (result is not None or kind == "flash" and error in BAD_EXTRACTION):
                        self.db.execute("""
                            INSERT INTO hotel_step_cache (client_id, fingerprint, step, saved_at, response, failure)
                            VALUES (?, ?, ?, ?, ?, ?)
                            ON CONFLICT(client_id, fingerprint, step) DO UPDATE SET
                                saved_at = excluded.saved_at, response = excluded.response, failure = excluded.failure
                        """, (*self.work, step, int(time.time()), encode(result), error))
            await asyncio.sleep(0.5)

    async def web_tool(self, kind, body, *, ledger_kind=None):
        async def request(payload):
            try:
                async with asyncio.timeout(14), self.provider.stream(
                    "POST", "/v1/tools/" + kind, json=payload, timeout=None,
                ) as response:
                    status = response.status_code
                    if status != 200:
                        code = {401: "authorization", 402: "balance", 403: "source_blocked", 404: "source_unavailable"}.get(
                            status, kind + "_http")
                        raise SearchInterrupted(code, status >= 500 or status in (408, 429))
                    data = bytearray()
                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        data.extend(chunk)
                        if len(data) > 1_000_000:
                            raise SearchInterrupted(kind + "_response_limit")
                result = json.loads(data)
            except (TimeoutError, httpx.HTTPError):
                raise SearchInterrupted(kind + "_unavailable", True) from None
            except (ValueError, RecursionError):
                raise SearchInterrupted(kind + "_response", True) from None
            if not isinstance(result, dict) or result.get("error"):
                raise SearchInterrupted(kind + "_response", True)
            if kind == "fetch":
                content = result.get("content")
                if not isinstance(content, str) or not content.strip():
                    raise SearchInterrupted("source_unavailable")
                return {"title": short_text(result.get("title"), 300), "content": content[:40_000]}, None, 1
            rows = result.get("results")
            if not isinstance(rows, list):
                raise SearchInterrupted("search_response", True)
            return [
                {"url": short_text(row.get("url"), 2048), "title": short_text(row.get("title"), 300),
                 "content": short_text(row.get("content"), 16_000)}
                for row in rows[:SEARCH_RESULTS] if isinstance(row, dict)
            ], None, int(bool(rows))

        return await self.step(ledger_kind or kind, body, request)

    def previous_pages(self):
        if not self.work:
            return
        rows = self.db.execute("""
            SELECT step, response FROM hotel_step_cache WHERE client_id = ? AND fingerprint = ?
              AND saved_at >= ? AND failure IS NULL ORDER BY saved_at DESC, step
        """, (*self.work, int(time.time()) - REUSE_SECONDS)).fetchall()
        for step, body in rows:
            pages = json.loads(body)
            if isinstance(pages, list):
                for page in pages:
                    if isinstance(page, dict) and "url" in page and "content" in page:
                        yield step, page

    async def search(self, query):
        return await self.web_tool("search", {"query": query, "count": SEARCH_RESULTS, "need_content": True})

    async def enrich_search(self, query):
        return await self.web_tool("search", {"query": query, "count": SEARCH_RESULTS, "need_content": True}, ledger_kind="enrich_search")

    async def fetch(self, url):
        return await self.web_tool("fetch", {"url": url})

    @staticmethod
    def flash_body(instruction, data, max_tokens):
        return {
            "model": MODEL, "thinking": {"type": "disabled"}, "temperature": 0, "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": instruction},
                         {"role": "user", "content": encode(data)}],
        }

    async def flash(self, instruction, data, max_tokens):
        body = self.flash_body(instruction, data, max_tokens)
        async def request(payload):
            try:
                status, reply = await provider_reply(self.provider, payload)
            except AnalysisError as error:
                raise SearchInterrupted(error.code, error.retryable) from None
            usage = provider_usage(reply)
            choices = reply.get("choices")
            finish = (short_text(choices[0].get("finish_reason"), 40) or None
                      if isinstance(choices, list) and choices and isinstance(choices[0], dict) else None)
            if status == 200 and finish == "length":
                failure = SearchInterrupted("flash_truncated", usage=usage)
                failure.finish_reason = finish
                raise failure
            try:
                result = json.loads(provider_content(status, reply))
                if not isinstance(result, dict):
                    raise ValueError
            except (ValueError, TypeError, RecursionError, AnalysisError) as error:
                code = error.code if isinstance(error, AnalysisError) else "flash_response"
                failure = SearchInterrupted(code, code not in BAD_EXTRACTION and getattr(error, "retryable", False), usage)
                failure.finish_reason = finish
                raise failure from None
            return result, usage, None, finish

        return await self.step("flash", body, request)

    async def rates(self):
        previous = self.db.execute("""
            SELECT response FROM hotel_attempts WHERE client_id = ? AND task_id = ? AND kind = 'fx'
            AND response IS NOT NULL
        """, self.identity).fetchone()
        if previous:
            return json.loads(previous[0])
        now = int(time.time())
        cached = self.db.execute("SELECT document, received_at FROM hotel_fx_cache WHERE source = ?",
                                 (FX_URL,)).fetchone()
        if cached and cached[1] >= now - 6 * 3600:
            return json.loads(cached[0])

        async def request(_):
            try:
                response = await self.external.get(FX_URL, timeout=6)
                response.raise_for_status()
                if len(response.content) > 100_000:
                    raise ValueError
                root = ElementTree.fromstring(response.content)
                return {
                    "date": root.attrib["Date"],
                    "rates": {row.findtext("CharCode"): [row.findtext("Nominal"), row.findtext("Value")]
                              for row in root.findall("Valute")},
                }, None, None
            except (httpx.HTTPError, ValueError, KeyError, ElementTree.ParseError):
                raise SearchInterrupted("fx_unavailable", True) from None

        try:
            document = await self.step("fx", {"source": FX_URL}, request)
        except SearchInterrupted:
            if cached and cached[1] >= now - 3 * 86400:
                return json.loads(cached[0])
            raise
        self.db.execute("""
            INSERT INTO hotel_fx_cache (source, received_at, document) VALUES (?, ?, ?)
            ON CONFLICT(source) DO UPDATE SET received_at = excluded.received_at, document = excluded.document
            WHERE hotel_fx_cache.received_at <= excluded.received_at
        """, (FX_URL, now, encode(document)))
        return document


def short_text(value, length):
    return value.strip()[:length] if isinstance(value, str) else ""
