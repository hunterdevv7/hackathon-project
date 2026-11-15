"""End-to-end checks for the classical track. Standard library unittest only.

Run from the project root:
    python -m unittest discover tests -v
"""

import os
import random
import secrets
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import server  # noqa: E402
from classical_rng import (  # noqa: E402
    BATCH_SIZE,
    classical_draw,
    generate_bits,
    recover_seed,
    replay,
    validate_seed,
)
from randomness_tests import (  # noqa: E402
    frequency_test,
    runs_test,
    score_bits,
    validate_bits,
)


def secret_bits(n: int = BATCH_SIZE) -> list[int]:
    return [int(c) for c in format(secrets.randbits(n), f"0{n}b")]


class TestReplay(unittest.TestCase):
    def test_replay_matches_draw(self):
        draw = classical_draw(1234)
        self.assertEqual(len(draw["bits"]), BATCH_SIZE)
        self.assertEqual(replay(1234), draw["bits"])

    def test_replay_over_many_seeds(self):
        rng = random.Random(0)
        for _ in range(1000):
            seed = rng.randrange(0, 2**32)
            self.assertEqual(replay(seed), classical_draw(seed)["bits"])

    def test_global_random_does_not_disturb_replay(self):
        draw = classical_draw(1234)
        random.seed(999)
        for _ in range(500):
            random.random()
        self.assertEqual(replay(1234), draw["bits"])

    def test_different_seeds_differ(self):
        self.assertNotEqual(generate_bits(1234), generate_bits(1235))

    def test_default_seed_is_time_based(self):
        draw = classical_draw()
        self.assertLessEqual(abs(draw["seed"] - int(time.time())), 2)
        self.assertEqual(draw["source"], "classical")

    def test_recover_unknown_time_seed(self):
        now = int(time.time())
        seed = now - 37
        self.assertEqual(recover_seed(generate_bits(seed), now=now), seed)

    def test_validate_seed_rejects_bad_values(self):
        for bad in (True, False, 1.0, "1", None, [1], -1):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    validate_seed(bad)
        self.assertEqual(validate_seed(0), 0)


class TestRandomness(unittest.TestCase):
    def test_fixed_seed_prng_passes(self):
        self.assertTrue(score_bits(generate_bits(1234))["pass"])

    def test_secrets_batch_passes(self):
        # Re-draw once so a single unlucky batch (about 2% chance) can't fail the run.
        ok = score_bits(secret_bits())["pass"] or score_bits(secret_bits())["pass"]
        self.assertTrue(ok)

    def test_secrets_pass_rate(self):
        # Expected rate is about 98% (two tests at alpha = 0.01, plus the
        # discreteness of n = 100). 1000 batches keeps the chance of a
        # spurious failure negligible.
        batches = 1000
        passed = sum(score_bits(secret_bits())["pass"] for _ in range(batches))
        self.assertGreater(passed / batches, 0.95)

    def test_all_zeros_fail(self):
        result = score_bits([0] * 100)
        self.assertFalse(result["pass"])

    def test_biased_fails_frequency(self):
        bits = [1] * 80 + [0] * 20
        random.Random(1).shuffle(bits)
        self.assertLess(frequency_test(bits), 0.01)
        self.assertFalse(score_bits(bits)["pass"])

    def test_alternating_passes_frequency_but_fails_runs(self):
        bits = [0, 1] * 50
        self.assertGreaterEqual(frequency_test(bits), 0.01)
        self.assertLess(runs_test(bits), 0.01)
        self.assertFalse(score_bits(bits)["pass"])

    def test_score_shape(self):
        result = score_bits(generate_bits(1234))
        self.assertEqual(set(result), {"pass", "score", "tests"})
        self.assertIsInstance(result["pass"], bool)
        self.assertTrue(0.0 <= result["score"] <= 1.0)
        self.assertEqual(set(result["tests"]), {"frequency", "runs"})

    def test_validate_bits_rejects_bad_input(self):
        for bad in ([], [2], [True, False], [0.0], "0101", None, [0] * 100_001):
            with self.subTest(bad=type(bad).__name__):
                with self.assertRaises(ValueError):
                    validate_bits(bad)


class TestAPI(unittest.TestCase):
    def setUp(self):
        server.app.testing = True
        self.client = server.app.test_client()
        server._last_draw = None
        server.unregister_source("quantum")

    def tearDown(self):
        server.unregister_source("quantum")

    def test_draw_shape(self):
        resp = self.client.get("/classical-draw")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(set(data), {"bits", "seed", "source"})
        self.assertEqual(data["source"], "classical")
        self.assertEqual(len(data["bits"]), BATCH_SIZE)
        self.assertIsInstance(data["seed"], int)
        self.assertEqual(resp.headers["Access-Control-Allow-Origin"], "*")

    def test_draw_with_seed_param(self):
        data = self.client.get("/classical-draw?seed=1234").get_json()
        self.assertEqual(data["seed"], 1234)
        self.assertEqual(data["bits"], generate_bits(1234))

    def test_draw_bad_seed_param(self):
        for bad in ("abc", "-5", "1.0", ""):
            with self.subTest(bad=bad):
                resp = self.client.get(f"/classical-draw?seed={bad}")
                self.assertEqual(resp.status_code, 400)
                self.assertIn("error", resp.get_json())

    def test_replay_over_http_matches_draw(self):
        draw = self.client.get("/classical-draw").get_json()
        resp = self.client.post("/classical-draw/replay", json={"seed": draw["seed"]})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json(), draw)

    def test_replay_bad_seeds(self):
        for body in ({"seed": "abc"}, {"seed": True}, {"seed": 1.5}, {}, None):
            with self.subTest(body=body):
                if body is None:
                    resp = self.client.post("/classical-draw/replay", data="not json",
                                            content_type="application/json")
                else:
                    resp = self.client.post("/classical-draw/replay", json=body)
                self.assertEqual(resp.status_code, 400)
                self.assertIn("error", resp.get_json())

    def test_stat_test_classical_scores_last_draw(self):
        self.client.get("/classical-draw?seed=1234")
        resp = self.client.get("/stat-test?source=classical")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json(), score_bits(generate_bits(1234)))

    def test_stat_test_classical_without_prior_draw(self):
        resp = self.client.get("/stat-test?source=classical")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(set(resp.get_json()), {"pass", "score", "tests"})

    def test_stat_test_quantum_before_and_after_register(self):
        resp = self.client.get("/stat-test?source=quantum")
        self.assertEqual(resp.status_code, 503)
        self.assertEqual(resp.get_json(), {"error": "quantum source not connected"})

        server.register_source("quantum", lambda: generate_bits(42))
        resp = self.client.get("/stat-test?source=quantum")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(set(resp.get_json()), {"pass", "score", "tests"})

    def test_stat_test_quantum_bad_output(self):
        server.register_source("quantum", lambda: [0, 2, 1])
        self.assertEqual(self.client.get("/stat-test?source=quantum").status_code, 502)

    def test_stat_test_unknown_source(self):
        self.assertEqual(self.client.get("/stat-test?source=dice").status_code, 400)

    def test_post_stat_test(self):
        resp = self.client.post("/stat-test", json={"bits": generate_bits(1234)})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.get_json()["pass"])

        resp = self.client.post("/stat-test", json={"bits": [0, 1] * 50})
        self.assertFalse(resp.get_json()["pass"])

    def test_post_stat_test_invalid(self):
        for body in ({"bits": []}, {"bits": [0, 3]}, {"bits": "0101"}, {}):
            with self.subTest(body=body):
                resp = self.client.post("/stat-test", json=body)
                self.assertEqual(resp.status_code, 400)
                self.assertIn("error", resp.get_json())


if __name__ == "__main__":
    unittest.main()
