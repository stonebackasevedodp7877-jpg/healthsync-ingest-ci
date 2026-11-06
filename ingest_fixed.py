"""HealthSync alert-ingest service (Lab 9 reference solution).

Fixes every finding in the starter: per-device credentials bound to device_id,
constant-time comparison, a separate admin credential, size and schema limits,
parameterized SQL, generic error responses, an audit trail, and PHI-free logs.
"""
import hmac
import json
import logging
import re
import sqlite3
import time

# In production these come from a secret manager, never from source code.
DEVICE_KEYS = {"dev-001": "k-dev-001-secret", "dev-002": "k-dev-002-secret"}
ADMIN_TOKENS = {"admin-token-abc": "care-admin-1"}

MAX_BODY = 8 * 1024
KIND_RANGES = {"heart_rate": (20, 250), "glucose": (20, 600)}
ID_PATTERN = re.compile(r"^[A-Za-z0-9-]{1,32}$")

DB = sqlite3.connect(":memory:", check_same_thread=False)
DB.execute("CREATE TABLE readings (device_id TEXT, patient_id TEXT, kind TEXT, value REAL, ts INTEGER)")
DB.execute("CREATE TABLE audit (who TEXT, action TEXT, ts INTEGER)")

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("ingest")


def _same(a, b):
    return hmac.compare_digest(a.encode(), b.encode())


def _authenticate_device(headers):
    device_id = headers.get("X-Device-Id", "")
    expected = DEVICE_KEYS.get(device_id)
    if expected is None or not _same(headers.get("X-Api-Key", ""), expected):
        return None
    return device_id


def _authenticate_admin(headers):
    supplied = headers.get("X-Admin-Token", "")
    for token, who in ADMIN_TOKENS.items():
        if _same(supplied, token):
            return who
    return None


def handle_reading(headers, raw_body):
    """POST /v1/readings -> (status, json-able response)"""
    device = _authenticate_device(headers)
    if device is None:
        return 401, {"error": "unauthorized"}
    if len(raw_body) > MAX_BODY:
        return 413, {"error": "payload too large"}
    try:
        body = json.loads(raw_body)
        if not isinstance(body, dict):
            return 400, {"error": "invalid request"}
        patient_id, kind, value = body.get("patient_id"), body.get("kind"), body.get("value")
        if body.get("device_id") != device:
            log.warning("device %s attempted to report as another device", device)
            return 403, {"error": "forbidden"}
        if not (isinstance(patient_id, str) and ID_PATTERN.match(patient_id)):
            return 400, {"error": "invalid request"}
        # Lab 10 fix: type-check kind BEFORE the dict lookup; a list/dict kind is
        # unhashable and used to raise TypeError -> 500 (see test_regression.py).
        if not isinstance(kind, str) or kind not in KIND_RANGES:
            return 400, {"error": "invalid request"}
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return 400, {"error": "invalid request"}
        low, high = KIND_RANGES[kind]
        if not low <= value <= high:
            return 400, {"error": "invalid request"}
        DB.execute(
            "INSERT INTO readings VALUES (?, ?, ?, ?, ?)",
            (device, patient_id, kind, float(value), int(time.time())),
        )
        log.info("reading stored device=%s kind=%s", device, kind)  # no patient data in logs
        return 201, {"status": "stored"}
    except ValueError:
        return 400, {"error": "invalid request"}
    except Exception:
        log.exception("unexpected error while storing reading")  # detail stays server-side
        return 500, {"error": "internal error"}


def handle_admin_export(headers, patient_id):
    """GET /admin/export?patient_id=... -> (status, json-able response)"""
    who = _authenticate_admin(headers)
    if who is None:
        return 401, {"error": "unauthorized"}
    if not ID_PATTERN.match(patient_id or ""):
        return 400, {"error": "invalid request"}
    DB.execute("INSERT INTO audit VALUES (?, ?, ?)", (who, "export:" + patient_id, int(time.time())))
    rows = DB.execute("SELECT * FROM readings WHERE patient_id = ?", (patient_id,)).fetchall()
    return 200, {"rows": rows}
