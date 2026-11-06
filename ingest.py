"""HealthSync alert-ingest service (Lab 9 starter).

Receives readings from wearable devices and serves an admin export.
NOTE: this file is intentionally flawed. Do not deploy it.
"""
import json
import logging
import sqlite3
import time
import traceback

API_KEY = "hs-device-key-2024"  # one key, printed on every device's firmware label

DB = sqlite3.connect(":memory:", check_same_thread=False)
DB.execute("CREATE TABLE readings (device_id TEXT, patient_id TEXT, kind TEXT, value REAL, ts INTEGER)")
DB.execute("CREATE TABLE audit (who TEXT, action TEXT, ts INTEGER)")

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("ingest")


def handle_reading(headers, raw_body):
    """POST /v1/readings -> (status, json-able response)"""
    if headers.get("X-Api-Key") != API_KEY:
        return 401, {"error": "unauthorized"}
    try:
        body = json.loads(raw_body)
        log.info("reading received: %s", body)
        device_id = body["device_id"]
        DB.execute(
            "INSERT INTO readings VALUES ('%s', '%s', '%s', %s, %d)"
            % (device_id, body["patient_id"], body["kind"], body["value"], int(time.time()))
        )
        return 201, {"status": "stored"}
    except Exception as e:
        return 500, {"error": str(e), "trace": traceback.format_exc()}


def handle_admin_export(headers, patient_id):
    """GET /admin/export?patient_id=... -> (status, json-able response)"""
    if headers.get("X-Api-Key") != API_KEY:
        return 401, {"error": "unauthorized"}
    rows = DB.execute(
        "SELECT * FROM readings WHERE patient_id = '%s'" % patient_id
    ).fetchall()
    return 200, {"rows": rows}
