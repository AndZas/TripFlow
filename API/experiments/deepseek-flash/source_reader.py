"""Read public HTML and PDF documents used as evidence."""

import ipaddress
import os
import re
import shutil
import socket
import subprocess
from contextlib import ExitStack, closing
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

import pypdfium2 as pdfium
from playwright.sync_api import Error as BrowserError, sync_playwright


@lru_cache(maxsize=256)
def public_host(host):
    try:
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except OSError:
        return False
    return bool(addresses) and all(ipaddress.ip_address(info[4][0]).is_global for info in addresses)


def public_url(url):
    try:
        p = urlsplit(url)
        return (p.scheme == "https" and p.hostname and not p.username and not p.password
                and p.port in (None, 443) and public_host(p.hostname))
    except ValueError:
        return False


class PublicRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not public_url(newurl) or site(newurl) != site(req.full_url):
            raise ValueError("redirect outside the source domain")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def site(url):
    return (urlsplit(url).hostname or "").removeprefix("www.")


def normalized_lines(text):
    return [" ".join(line.split()) for line in text.splitlines() if line.strip()]


def ocr(page):
    executable = os.environ.get("TRIPFLOW_TESSERACT") or shutil.which("tesseract")
    if not executable:
        executable = Path("C:/Program Files/Tesseract-OCR/tesseract.exe")
        if not executable.is_file():
            raise ValueError("scanned PDF requires Tesseract")
    data = Path(os.environ.get("TRIPFLOW_TESSDATA", Path(__file__).parent / ".venv/tessdata"))
    command = [str(executable), "stdin", "stdout", "-l", os.environ.get("TRIPFLOW_OCR_LANG", "rus")]
    if data.is_dir():
        command.extend(["--tessdata-dir", str(data)])
    scale = min(2.5, 2200 / max(page.get_width(), page.get_height()))
    buffer = BytesIO()
    with closing(page.render(scale=scale)) as bitmap:
        bitmap.to_pil().save(buffer, format="PNG")
    result = subprocess.run(command, input=buffer.getvalue(), capture_output=True, timeout=12, check=False)
    if result.returncode:
        raise ValueError("Tesseract could not read page; check the installed OCR language")
    return result.stdout.decode("utf-8", errors="replace")


def pdf_pages(raw):
    with pdfium.PdfDocument(raw) as document:
        for index in range(min(len(document), 30)):
            with closing(document[index]) as page:
                with closing(page.get_textpage()) as text_page:
                    text = text_page.get_text_bounded()
                mode = "pdf_text"
                if len(re.findall(r"[A-Za-zА-Яа-яЁё]", text)) < 35 and index < 4:
                    text, mode = ocr(page), "pdf_ocr"
                if lines := normalized_lines(text):
                    yield {"page": index + 1, "mode": mode, "lines": lines}


class Reader:
    def __init__(self):
        self.stack = ExitStack()
        self.browser = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.stack.close()

    def render(self, url):
        if self.browser is None:
            runtime = self.stack.enter_context(sync_playwright())
            channel = os.environ.get("TRIPFLOW_BROWSER_CHANNEL")
            edge = Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe")
            if channel is None and edge.is_file():
                channel = "msedge"
            self.browser = runtime.chromium.launch(channel=channel or None,
                                                   headless=True, chromium_sandbox=True)
            self.stack.callback(self.browser.close)
        with self.browser.new_context(accept_downloads=False, service_workers="block") as context:
            def route_request(route):
                request = route.request
                if (request.method not in ("GET", "HEAD") or request.resource_type in ("image", "media", "font")
                        or not public_url(request.url)
                        or request.is_navigation_request() and site(request.url) != site(url)):
                    route.abort()
                else:
                    route.continue_()

            context.route("**/*", route_request)
            page = context.new_page()
            response = page.goto(url, wait_until="domcontentloaded", timeout=10000)
            if not response or not response.ok:
                raise ValueError(f"browser HTTP {response.status if response else 'unknown'}")
            page.wait_for_timeout(1600)
            text = page.locator("body").inner_text(timeout=3000)[:160000]
            links = page.locator("a[href]").evaluate_all(
                "(elements) => elements.slice(0, 300).map(a => [a.href, a.innerText])"
            )
            return normalized_lines(text), links

    def read(self, url, parse_html, relevant, *, render=False):
        result = {"url": url, "state": "unreadable"}
        if not public_url(url):
            return {**result, "error": "not a public HTTPS URL"}
        try:
            parts = urlsplit(url)
            wire_url = urlunsplit((parts.scheme, parts.netloc, quote(parts.path, safe="/%+"),
                                   quote(parts.query, safe="=&%+"), ""))
            request = Request(wire_url, headers={"User-Agent": "TripFlow-LocalResearch/1.0"})
            with build_opener(PublicRedirect()).open(request, timeout=7) as response:
                content_type = response.headers.get_content_type()
                result.update(http=response.status, contentType=content_type)
                raw = response.read(8_000_001)
                charset = response.headers.get_content_charset()
            if len(raw) > 8_000_000:
                raise ValueError("source larger than 8 MB")
            if raw.startswith(b"%PDF-"):
                sections = list(pdf_pages(raw))
                if not sections:
                    raise ValueError("no readable PDF text")
                return {**result, "state": "readable", "method": "pdf", "sections": sections, "links": []}
            if content_type != "text/html":
                raise ValueError("unsupported media or URL did not return PDF")
            lines, links = parse_html(raw.decode(charset or "utf-8", errors="replace"))
            static = (lines, links)
            if render and (not usable(lines) or not any(relevant(line) for line in lines)):
                if challenge(" ".join(lines)):
                    raise ValueError("access challenge")
                try:
                    rendered = self.render(url)
                    if usable(rendered[0]) and (not usable(lines) or any(relevant(line) for line in rendered[0])):
                        lines, links = rendered
                        result["method"] = "javascript"
                except (BrowserError, OSError, ValueError) as error:
                    result["renderError"] = str(error).splitlines()[0]
                    lines, links = static
            if parts.path.lower().endswith(".pdf"):
                raise ValueError("PDF URL returned HTML")
            if not usable(lines):
                raise ValueError("no usable HTML text")
            return {**result, "state": "readable", "method": result.get("method", "html"),
                    "sections": [{"page": None, "lines": lines}], "links": links}
        except (OSError, ValueError, LookupError, pdfium.PdfiumError, subprocess.SubprocessError) as error:
            return {**result, "error": str(error)}


def challenge(text):
    return bool(re.search(r"проверяем ваш браузер|подтвердите, что вы не робот|just a moment|verify you are human|"
                          r"access denied|включите cookies", text[:1500], re.I))


def usable(lines):
    text = " ".join(lines)
    return len(text) >= 100 and not challenge(text)
