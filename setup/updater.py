#!/usr/bin/env python3
"""OpenClaw VPS Updater — lightweight host-side update service.

Exposes authenticated endpoints to trigger OpenClaw updates:
  POST /api/update        — start update (returns 202, runs in background)
  GET  /api/update/status — poll update progress
  GET  /health            — health check

Runs as a systemd service on 127.0.0.1:18788 (localhost only, proxied via nginx).
Authenticated via the same gateway token at /var/lib/openclaw-token.
"""

import json
import os
import subprocess
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

OPENCLAW_DIR = "/opt/openclaw"
TOKEN_FILE = "/var/lib/openclaw-token"
BIND_HOST = "127.0.0.1"
BIND_PORT = 18788

update_state = {
    "status": "idle",
    "started_at": None,
    "finished_at": None,
    "log": [],
    "error": None,
}
update_lock = threading.Lock()


def read_token():
    try:
        with open(TOKEN_FILE, "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        return None


def run_update():
    global update_state

    with update_lock:
        if update_state["status"] == "running":
            return
        update_state = {
            "status": "running",
            "started_at": time.time(),
            "finished_at": None,
            "log": [],
            "error": None,
        }

    def _log(msg):
        update_state["log"].append({"time": time.time(), "msg": msg})

    def _run_step(description, cmd, timeout=300):
        _log(f"Starting: {description}")
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=OPENCLAW_DIR,
            )
            if result.returncode != 0:
                _log(f"FAILED: {description}")
                _log(f"stderr: {result.stderr[:1000]}")
                raise RuntimeError(f"{description} failed: {result.stderr[:500]}")
            _log(f"OK: {description}")
            return result
        except subprocess.TimeoutExpired:
            _log(f"TIMEOUT: {description}")
            raise RuntimeError(f"{description} timed out")

    MAX_TAG_FALLBACK = 5

    try:
        # Buscar todas as tags do upstream
        _run_step(
            "git fetch origin --tags",
            ["git", "fetch", "origin", "--tags"],
            timeout=60,
        )

        # Listar tags de release ordenadas por versao (mais recente primeiro)
        tags_result = subprocess.run(
            ["git", "tag", "-l", "v20*", "--sort=-version:refname"],
            capture_output=True, text=True, timeout=10,
            cwd=OPENCLAW_DIR,
        )
        tags = [t.strip() for t in tags_result.stdout.strip().split("\n") if t.strip()]

        if not tags:
            raise RuntimeError("Nenhuma tag de release encontrada no upstream")

        _log(f"Tags disponiveis: {', '.join(tags[:5])}...")

        # Tentar buildar da tag mais recente ate MAX_TAG_FALLBACK
        build_ok = False
        for tag in tags[:MAX_TAG_FALLBACK]:
            _log(f"Tentando build da tag {tag}...")
            subprocess.run(
                ["git", "checkout", tag, "--quiet"],
                capture_output=True, timeout=30,
                cwd=OPENCLAW_DIR,
            )
            try:
                _run_step(
                    f"docker build -t openclaw:local ({tag})",
                    ["docker", "build", "-t", "openclaw:local", "-f", "Dockerfile", "."],
                    timeout=600,
                )
                build_ok = True
                _log(f"Build OK na tag {tag}")
                break
            except RuntimeError:
                _log(f"Build falhou na tag {tag}, tentando anterior...")
                continue

        # Voltar ao main
        subprocess.run(
            ["git", "checkout", "main", "--quiet"],
            capture_output=True, timeout=30,
            cwd=OPENCLAW_DIR,
        )

        if not build_ok:
            raise RuntimeError(
                f"Nenhuma das ultimas {MAX_TAG_FALLBACK} tags buildou com sucesso"
            )

        # Prune old images to save disk space
        subprocess.run(
            ["docker", "image", "prune", "-f"],
            capture_output=True,
            timeout=30,
            cwd=OPENCLAW_DIR,
        )
        _run_step(
            "docker compose down",
            ["docker", "compose", "down"],
            timeout=120,
        )
        _run_step(
            "docker compose up -d",
            ["docker", "compose", "up", "-d"],
            timeout=120,
        )

        update_state["status"] = "success"
        update_state["finished_at"] = time.time()
        _log("Update completed successfully.")

    except Exception as e:
        update_state["status"] = "error"
        update_state["error"] = str(e)
        update_state["finished_at"] = time.time()
        _log(f"Update failed: {e}")


class UpdateHandler(BaseHTTPRequestHandler):
    def _check_auth(self):
        # Requests vindos via Nginx proxy (header interno, so acessivel via localhost)
        if self.headers.get("X-Openclaw-Internal") == "true":
            return True

        token = read_token()
        if not token:
            self._respond(500, {"error": "Token file not found"})
            return False

        auth = self.headers.get("Authorization", "")
        if auth.startswith("Bearer ") and auth[7:] == token:
            return True

        qs = parse_qs(urlparse(self.path).query)
        if qs.get("token", [None])[0] == token:
            return True

        self._respond(401, {"error": "Unauthorized"})
        return False

    def _respond(self, code, body):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.end_headers()

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/update":
            if not self._check_auth():
                return
            if update_state["status"] == "running":
                self._respond(409, {
                    "error": "Update already in progress",
                    "status": update_state,
                })
                return
            thread = threading.Thread(target=run_update, daemon=True)
            thread.start()
            self._respond(202, {"message": "Update started", "status": "running"})
        else:
            self._respond(404, {"error": "Not found"})

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/update/status":
            if not self._check_auth():
                return
            self._respond(200, update_state)
        elif path == "/health":
            self._respond(200, {"status": "ok"})
        else:
            self._respond(404, {"error": "Not found"})

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    server = HTTPServer((BIND_HOST, BIND_PORT), UpdateHandler)
    print(f"OpenClaw Updater listening on {BIND_HOST}:{BIND_PORT}")
    server.serve_forever()
