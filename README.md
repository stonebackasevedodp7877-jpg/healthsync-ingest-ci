# healthsync-ingest-ci (CS565 Lab 10)

Python 3 standard library only; Bandit is the one tool to install (`pip install bandit==1.9.4`).

    bandit ingest.py server.py                                  # SAST
    python3 server.py --port 8080                               # start the service (vulnerable ingest.py)
    python3 dast_probe.py http://127.0.0.1:8080                 # DAST probe
    python3 fuzz.py http://127.0.0.1:8080                       # fuzzer (seed 1, 300 inputs)

To test the fixed version, start the server with `INGEST_MODULE=ingest_fixed` and pass
`--device-key k-dev-001-secret` (and `--admin-token admin-token-abc` to the probe).

Only run dast_probe.py and fuzz.py against services you own or are authorized to test.
