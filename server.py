"""Minimal HTTP wrapper around ingest.py so it can be scanned and probed.

    python3 server.py [--host 127.0.0.1] [--port 8080]

POST /v1/readings          body = JSON reading
GET  /admin/export?patient_id=...
"""
import argparse
import importlib
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

# INGEST_MODULE lets you point the server at ingest_fixed.py instead of ingest.py
ingest = importlib.import_module(os.environ.get("INGEST_MODULE", "ingest"))


class Handler(BaseHTTPRequestHandler):
    def _send(self, status, payload):
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        if urlparse(self.path).path != "/v1/readings":
            return self._send(404, {"error": "not found"})
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8", errors="replace")
        status, payload = ingest.handle_reading(self.headers, raw)
        self._send(status, payload)

    def do_GET(self):
        url = urlparse(self.path)
        if url.path != "/admin/export":
            return self._send(404, {"error": "not found"})
        patient_id = parse_qs(url.query).get("patient_id", [""])[0]
        status, payload = ingest.handle_admin_export(self.headers, patient_id)
        self._send(status, payload)

    def log_message(self, fmt, *args):  # keep the console quiet
        pass


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8080)
    a = ap.parse_args()
    print(f"listening on http://{a.host}:{a.port}", flush=True)
    HTTPServer((a.host, a.port), Handler).serve_forever()
