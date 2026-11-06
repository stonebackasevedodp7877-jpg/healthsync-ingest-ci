"""Small mutation fuzzer for POST /v1/readings (Lab 10).

Takes a valid reading, mutates it in many ways, and reports every input that
makes the server answer 5xx. Seeded, so results repeat.

    python3 fuzz.py http://127.0.0.1:8080 [--n 300] [--seed 1]
        [--device-id dev-001] [--device-key KEY]

Exit code 0 = no 5xx responses, 1 = at least one.
"""
import argparse
import json
import random
import re
import sys
import urllib.error
import urllib.request

SEED = {"device_id": "dev-001", "patient_id": "p-100", "kind": "heart_rate", "value": 72}
ODD = [None, True, False, 0, -1, 1e308, 10 ** 400, "", " ", "A" * 5000, "'", "\"; DROP TABLE readings;--",
       "\u0000", "‮é", [], [1, 2], {}, {"a": {"b": 1}}, "%s%s%s", "../../etc/passwd"]


def mutate(rng):
    kind = rng.choice(["field", "drop", "extra", "raw", "toplevel"])
    body = dict(SEED)
    if kind == "field":
        body[rng.choice(list(SEED))] = rng.choice(ODD)
    elif kind == "drop":
        body.pop(rng.choice(list(SEED)))
    elif kind == "extra":
        body[rng.choice(["x", "admin", "__proto__", "kind\u0000"])] = rng.choice(ODD)
    elif kind == "toplevel":
        return json.dumps(rng.choice([[], [body], 1, "s", None, True]))
    else:
        text = json.dumps(body)
        return rng.choice([text[: rng.randrange(1, len(text))], text + "}", "", "\xff\xfe", text.replace('"', "'")])
    try:
        return json.dumps(body)
    except (ValueError, OverflowError):
        return "{}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--device-id", default="dev-001")
    ap.add_argument("--device-key", default="hs-device-key-2024")
    a = ap.parse_args()
    rng = random.Random(a.seed)
    headers = {"X-Device-Id": a.device_id, "X-Api-Key": a.device_key, "Content-Type": "application/json"}
    counts, bad = {}, {}
    for _ in range(a.n):
        body = mutate(rng)
        req = urllib.request.Request(a.base + "/v1/readings", data=body.encode("utf-8", "replace"), method="POST", headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                status, text = r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            status, text = e.code, e.read().decode("utf-8", "replace")
        counts[status] = counts.get(status, 0) + 1
        if status >= 500:
            try:
                reason = json.loads(text).get("error", "?")
            except ValueError:
                reason = "?"
            bad.setdefault(re.sub(r"\d+", "N", reason)[:40], body[:80])
    print("status counts:", dict(sorted(counts.items())))
    for reason, sample in bad.items():
        print(f"5xx  reason={reason!r}  example input={sample!r}")
    print(f"{sum(c for s, c in counts.items() if s >= 500)} server error(s) in {a.n} inputs, seed {a.seed}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
