"""Test harness: seeds a throw-away database and runs the real HTTP server in a
background thread, with a small cookie-aware JSON client."""
from __future__ import annotations

import http.cookiejar
import json
import shutil
import tempfile
import threading
import urllib.error
import urllib.request
from pathlib import Path

from kizuna.api import create_app
from kizuna.config import load_settings
from kizuna.logging_setup import setup_logging
from kizuna.seed.seeder import seed
from kizuna.web import make_server


class Client:
    def __init__(self, base: str):
        self.base = base
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def request(self, method: str, path: str, body=None, headers=None, raw: bytes | None = None, csrf: bool = True):
        h = {"X-Kizuna-Client": "web"} if csrf else {}
        h.update(headers or {})
        data = None
        if raw is not None:
            data = raw
        elif body is not None:
            data = json.dumps(body).encode()
            h["Content-Type"] = "application/json"
        req = urllib.request.Request(self.base + path, data=data, method=method, headers=h)
        try:
            with self.opener.open(req, timeout=30) as resp:
                payload = resp.read()
                ctype = resp.headers.get("Content-Type", "")
                return resp.status, (json.loads(payload) if "json" in ctype and payload else payload.decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            with e:
                payload = e.read()
            try:
                return e.code, json.loads(payload)
            except ValueError:
                return e.code, payload.decode("utf-8", "replace")

    def get(self, path, **kw):
        return self.request("GET", path, **kw)

    def post(self, path, body=None, **kw):
        return self.request("POST", path, body if body is not None else {}, **kw)

    def put(self, path, body=None, **kw):
        return self.request("PUT", path, body if body is not None else {}, **kw)

    def patch(self, path, body=None, **kw):
        return self.request("PATCH", path, body if body is not None else {}, **kw)

    def as_user(self, user_id: str) -> "Client":
        status, _ = self.post("/api/auth/demo-login", {"user_id": user_id})
        assert status == 200, f"demo login failed for {user_id}"
        return self


class LiveServer:
    def __init__(self):
        setup_logging("WARNING", json_mode=False)
        self.tmp = Path(tempfile.mkdtemp(prefix="kizuna-test-"))
        self.settings = load_settings(env_file=self.tmp / "none.env", data_dir=self.tmp, db_path=self.tmp / "test.db",
                                      upload_dir=self.tmp / "uploads", host="127.0.0.1", port=0, demo_mode=True,
                                      anthropic_enabled=False, log_level="WARNING")
        seed(self.settings.db_path, self.settings.upload_dir, fast_hash=True, settings=self.settings)
        self.app = create_app(self.settings)
        self.server = make_server(self.app, "127.0.0.1", 0)
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def client(self, user_id: str | None = None) -> Client:
        c = Client(self.base)
        return c.as_user(user_id) if user_id else c

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        shutil.rmtree(self.tmp, ignore_errors=True)
