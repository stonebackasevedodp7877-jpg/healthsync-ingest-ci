"""Tiny DAST probe for the HealthSync ingest service (Lab 10).

Sends attack requests to a RUNNING server and reports findings.
Only run it against systems you own or are authorized to test.

    python3 dast_probe.py http://127.0.0.1:8080 [--device-id dev-001]
        [--device-key KEY] [--admin-token TOKEN]

Exit code 0 = no findings, 1 = at least one finding.
"""
import argparse
import json
import sys
import urllib.error
import urllib.request


def call(base, method, path, headers=None, body=None):
    data = body.encode() if isinstance(body, str) else body
    req = urllib.request.Request(base + path, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("--device-id", default="dev-001")
    ap.add_argument("--device-key", default="hs-device-key-2024")
    ap.add_argument("--admin-token", default="admin-token-abc")
    a = ap.parse_args()

    dev = {"X-Device-Id": a.device_id, "X-Api-Key": a.device_key, "Content-Type": "application/json"}
    # admin requests carry both credentials so the same probe works on the starter and the fixed code
    adm = {"X-Admin-Token": a.admin_token, "X-Api-Key": a.device_key}
    ok = lambda pid, **kw: json.dumps({"device_id": a.device_id, "patient_id": pid, "kind": "heart_rate", "value": 72, **kw})
    findings = []

    def check(check_id, title, failed, detail):
        print(f"{'FINDING' if failed else 'ok     '} {check_id}  {title}" + (f"\n         {detail}" if failed else ""))
        if failed:
            findings.append(check_id)

    # seed two patients so injection results are observable
    call(a.base, "POST", "/v1/readings", dev, ok("p-1"))
    call(a.base, "POST", "/v1/readings", dev, ok("p-2"))

    s, _ = call(a.base, "POST", "/v1/readings", {"Content-Type": "application/json"}, ok("p-1"))
    check("D1", "unauthenticated reading is rejected", s != 401, f"expected 401, got {s}")

    s, b = call(a.base, "POST", "/v1/readings", dev, "{not valid json")
    check("D2", "malformed JSON gives 400 and no stack trace", s != 400 or "Traceback" in b,
          f"status {s}; body contains traceback: {'Traceback' in b}")

    s, _ = call(a.base, "POST", "/v1/readings", dev, json.dumps({"device_id": a.device_id}))
    check("D3", "missing fields give 400, not a server error", s != 400, f"expected 400, got {s}")

    s, _ = call(a.base, "POST", "/v1/readings", dev, ok("p-" + "9" * 20000))
    check("D4", "oversized body is refused (413 or 400)", s not in (400, 413), f"expected 413/400, got {s}")

    s, _ = call(a.base, "POST", "/v1/readings", dev, ok("p-1", value=99999))
    check("D5", "out-of-range value is rejected", s != 400, f"expected 400, got {s}")

    s, _ = call(a.base, "POST", "/v1/readings", dev, ok("p-1", device_id="dev-002"))
    check("D6", "a device cannot report as another device", s not in (401, 403), f"expected 401/403, got {s}")

    payload = "x' OR '1'='1"
    s, b = call(a.base, "GET", "/admin/export?patient_id=" + urllib.request.quote(payload), adm)
    leaked = 0
    try:
        leaked = len(json.loads(b).get("rows", []))
    except ValueError:
        pass
    check("D7", "SQL injection in patient_id returns nothing", s == 200 and leaked > 0,
          f"status {s}; {leaked} rows returned for an injected patient_id")

    s, _ = call(a.base, "GET", "/admin/export?patient_id=p-1", {k: v for k, v in dev.items() if k != "Content-Type"})
    check("D8", "a device credential cannot use the admin export", s == 200, f"expected 401/403, got {s}")

    print(f"\n{len(findings)} finding(s): {', '.join(findings) or 'none'}")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
