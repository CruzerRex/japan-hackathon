"""Minimal HTTP layer: request/response objects, router, errors, static files.

Kept deliberately small. Route handlers receive a `Request` and return either a
JSON-serialisable value (sent as 200 JSON), or a `Response`.
"""
from __future__ import annotations

import json
import logging
import mimetypes
import re
import time
import traceback
from dataclasses import dataclass, field
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, unquote, urlsplit

from .logging_setup import log

logger = logging.getLogger("kizuna.http")

MAX_JSON_BYTES = 2 * 1024 * 1024

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
    "Content-Security-Policy": (
        "default-src 'self'; img-src 'self' data: blob:; media-src 'self' blob:; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; script-src 'self'; "
        "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    ),
}


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, details: Any = None):
        super().__init__(message)
        self.status, self.code, self.message, self.details = status, code, message, details


def bad_request(message: str, details: Any = None, code: str = "invalid_input") -> ApiError:
    return ApiError(400, code, message, details)


def not_found(what: str = "Resource") -> ApiError:
    return ApiError(404, "not_found", f"{what} not found")


def forbidden(message: str = "You do not have permission to perform this action") -> ApiError:
    return ApiError(403, "forbidden", message)


def conflict(message: str, details: Any = None) -> ApiError:
    return ApiError(409, "conflict", message, details)


@dataclass
class Response:
    status: int = 200
    body: bytes | None = b""
    headers: dict = field(default_factory=dict)
    file_path: Path | None = None
    file_range: tuple[int, int] | None = None

    @classmethod
    def json(cls, data: Any, status: int = 200) -> "Response":
        return cls(status, json.dumps(data, ensure_ascii=False, default=str).encode("utf-8"),
                   {"Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store"})

    @classmethod
    def text(cls, text: str, content_type: str = "text/plain; charset=utf-8", status: int = 200,
             filename: str | None = None) -> "Response":
        headers = {"Content-Type": content_type, "Cache-Control": "no-store"}
        if filename:
            headers["Content-Disposition"] = f'attachment; filename="{filename}"'
        return cls(status, text.encode("utf-8"), headers)


class Request:
    def __init__(self, handler: BaseHTTPRequestHandler, app: "App"):
        self.handler = handler
        self.app = app
        self.method = handler.command
        parts = urlsplit(handler.path)
        self.path = unquote(parts.path)
        self.query = {k: v[-1] for k, v in parse_qs(parts.query).items()}
        self.headers = handler.headers
        self.params: dict[str, str] = {}
        self.user: dict | None = None
        self.db = None
        self._body: bytes | None = None
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get("Cookie", ""))
        except Exception:
            pass
        self.cookies = {k: m.value for k, m in cookie.items()}
        self.set_cookies: list[str] = []

    @property
    def content_length(self) -> int:
        try:
            return int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return 0

    def body(self, limit: int = MAX_JSON_BYTES) -> bytes:
        if self._body is None:
            n = self.content_length
            if n > limit:
                raise ApiError(413, "payload_too_large", f"Request body exceeds {limit // 1024} KB")
            self._body = self.handler.rfile.read(n) if n else b""
        return self._body

    def json(self) -> dict:
        raw = self.body()
        if not raw:
            return {}
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise bad_request("Request body is not valid JSON")
        if not isinstance(data, dict):
            raise bad_request("JSON body must be an object")
        return data

    def stream_to(self, fh, limit: int, chunk: int = 1024 * 1024) -> int:
        remaining = self.content_length
        if remaining <= 0:
            raise bad_request("Empty upload")
        if remaining > limit:
            raise ApiError(413, "payload_too_large", f"File exceeds the {limit // (1024 * 1024)} MB limit")
        total = 0
        while remaining > 0:
            data = self.handler.rfile.read(min(chunk, remaining))
            if not data:
                break
            fh.write(data)
            total += len(data)
            remaining -= len(data)
        self._body = b""
        return total


Handler = Callable[[Request], Any]


@dataclass
class Route:
    method: str
    pattern: re.Pattern
    handler: Handler
    auth: bool


class Router:
    def __init__(self):
        self.routes: list[Route] = []

    def add(self, method: str, path: str, handler: Handler, auth: bool = True) -> None:
        regex = "^" + re.sub(r"\{(\w+)\}", r"(?P<\1>[^/]+)", path) + "$"
        self.routes.append(Route(method, re.compile(regex), handler, auth))

    def route(self, method: str, path: str, auth: bool = True):
        def deco(fn: Handler) -> Handler:
            self.add(method, path, fn, auth)
            return fn
        return deco

    def match(self, method: str, path: str) -> tuple[Route | None, dict, bool]:
        path_exists = False
        for r in self.routes:
            m = r.pattern.match(path)
            if m:
                path_exists = True
                if r.method == method:
                    return r, m.groupdict(), True
        return None, {}, path_exists


class App:
    """Ties the router, middleware hooks and static file serving together."""

    def __init__(self, settings, router: Router, open_db: Callable, authenticate: Callable):
        self.settings = settings
        self.router = router
        self.open_db = open_db
        self.authenticate = authenticate

    # -- dispatch -----------------------------------------------------------
    def handle(self, handler: BaseHTTPRequestHandler) -> None:
        started = time.perf_counter()
        req = Request(handler, self)
        status = 500
        try:
            if req.path.startswith("/api/"):
                resp = self._dispatch_api(req)
            else:
                resp = self._static(req)
        except ApiError as e:
            resp = Response.json({"error": {"code": e.code, "message": e.message, "details": e.details}}, e.status)
        except Exception:
            log(logger, logging.ERROR, "unhandled_error", path=req.path, method=req.method,
                trace=traceback.format_exc(limit=8))
            resp = Response.json({"error": {"code": "internal_error",
                                            "message": "An unexpected server error occurred. It has been logged."}}, 500)
        finally:
            if req.db is not None:
                req.db.close()
        status = resp.status
        self._send(handler, req, resp)
        if req.path.startswith("/api/"):
            log(logger, logging.INFO, "request", method=req.method, path=req.path, status=status,
                ms=round((time.perf_counter() - started) * 1000, 1),
                user=(req.user or {}).get("id"))

    def _dispatch_api(self, req: Request) -> Response:
        route, params, path_exists = self.router.match(req.method, req.path)
        if not route:
            if path_exists:
                raise ApiError(405, "method_not_allowed", "Method not allowed")
            raise not_found("Endpoint")
        # CSRF defence: state-changing requests must carry the custom header that
        # only same-origin JavaScript can set (cookies are also SameSite=Strict).
        if req.method in ("POST", "PUT", "PATCH", "DELETE") and req.headers.get("X-Kizuna-Client") != "web":
            raise forbidden("Missing client header")
        req.params = params
        req.db = self.open_db()
        if route.auth:
            self.authenticate(req)
        result = route.handler(req)
        if isinstance(result, Response):
            return result
        return Response.json(result if result is not None else {"ok": True})

    def _static(self, req: Request) -> Response:
        if req.method not in ("GET", "HEAD"):
            raise ApiError(405, "method_not_allowed", "Method not allowed")
        web_dir: Path = self.settings.web_dir.resolve()
        rel = req.path.lstrip("/") or "index.html"
        target = (web_dir / rel).resolve()
        if web_dir not in target.parents and target != web_dir:
            raise not_found()
        if not target.is_file():
            if "." in Path(rel).name:
                raise not_found("File")
            target = web_dir / "index.html"  # SPA fallback
        ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript",):
            ctype += "; charset=utf-8"
        if target.suffix == ".js":
            ctype = "text/javascript; charset=utf-8"
        st = target.stat()
        etag = f'"{int(st.st_mtime_ns):x}-{st.st_size:x}"'
        headers = {"Content-Type": ctype, "Cache-Control": "no-cache", "ETag": etag}
        if req.headers.get("If-None-Match") == etag:
            return Response(304, b"", headers)
        return Response(200, None, headers, file_path=target)

    # -- output ---------------------------------------------------------------
    def _send(self, handler: BaseHTTPRequestHandler, req: Request, resp: Response) -> None:
        try:
            handler.send_response(resp.status, HTTPStatus(resp.status).phrase if resp.status in HTTPStatus._value2member_map_ else "")
            headers = {**SECURITY_HEADERS, **resp.headers}
            if req._body is None and req.content_length > 0:
                # Unread request body would corrupt the next keep-alive request.
                headers["Connection"] = "close"
                handler.close_connection = True
            body = resp.body or b""
            if resp.file_path is not None:
                size = resp.file_path.stat().st_size
                start, end = resp.file_range if resp.file_range else (0, size - 1)
                headers["Content-Length"] = str(max(0, end - start + 1))
            else:
                headers["Content-Length"] = str(len(body))
            for k, v in headers.items():
                handler.send_header(k, v)
            for c in req.set_cookies:
                handler.send_header("Set-Cookie", c)
            handler.end_headers()
            if req.method == "HEAD":
                return
            if resp.file_path is not None:
                start, end = resp.file_range if resp.file_range else (0, resp.file_path.stat().st_size - 1)
                with resp.file_path.open("rb") as fh:
                    fh.seek(start)
                    remaining = end - start + 1
                    while remaining > 0:
                        chunk = fh.read(min(256 * 1024, remaining))
                        if not chunk:
                            break
                        handler.wfile.write(chunk)
                        remaining -= len(chunk)
            else:
                handler.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass


def make_server(app: App, host: str, port: int) -> ThreadingHTTPServer:
    class _Handler(BaseHTTPRequestHandler):
        server_version = "KizunaForge"
        sys_version = ""
        protocol_version = "HTTP/1.1"

        def _go(self):
            app.handle(self)

        do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = do_HEAD = _go

        def log_message(self, fmt, *args):  # silence default stderr logging
            pass

    server = ThreadingHTTPServer((host, port), _Handler)
    server.daemon_threads = True
    return server
