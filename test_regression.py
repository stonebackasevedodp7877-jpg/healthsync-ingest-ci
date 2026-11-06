"""Regression test for the Lab 10 fuzzer finding in ingest_fixed.py.

Fuzzer (seed 1) input that caused HTTP 500:
    {"device_id": "dev-001", "patient_id": "p-100", "kind": [1, 2], "value": 72}

Root cause: "kind" was never type-checked, so a list/dict reached
`kind not in KIND_RANGES`, raised TypeError (unhashable type) and fell into
the generic handler (500) instead of being rejected as invalid input (400).

Run:  python3 -m unittest -v test_regression
"""
import json
import logging
import unittest

import ingest_fixed

HEADERS = {"X-Device-Id": "dev-001", "X-Api-Key": "k-dev-001-secret"}


def reading(**overrides):
    body = {"device_id": "dev-001", "patient_id": "p-100", "kind": "heart_rate", "value": 72}
    body.update(overrides)
    return json.dumps(body)


class KindTypeRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        logging.disable(logging.CRITICAL)  # keep test output readable

    @classmethod
    def tearDownClass(cls):
        logging.disable(logging.NOTSET)

    def test_list_kind_gives_400(self):
        status, body = ingest_fixed.handle_reading(HEADERS, reading(kind=[1, 2]))
        self.assertEqual(status, 400)
        self.assertEqual(body, {"error": "invalid request"})

    def test_unhashable_kinds_give_400(self):
        for kind in ([], [1, 2], {}, {"a": {"b": 1}}):
            with self.subTest(kind=kind):
                status, body = ingest_fixed.handle_reading(HEADERS, reading(kind=kind))
                self.assertEqual(status, 400)
                self.assertNotIn("trace", body)

    def test_valid_reading_gives_201(self):
        status, body = ingest_fixed.handle_reading(HEADERS, reading())
        self.assertEqual(status, 201)
        self.assertEqual(body, {"status": "stored"})


if __name__ == "__main__":
    unittest.main()
