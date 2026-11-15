import random

import pytest

from backend import stats
from backend.app import create_app


def _bits(s: str) -> list[int]:
    return [int(c) for c in s]


# --- Worked examples from NIST SP 800-22 -----------------------------------

def test_monobit_matches_nist_example():
    assert stats.monobit(_bits("1011010101")) == pytest.approx(0.527089, abs=1e-6)


def test_runs_matches_nist_example():
    assert stats.runs(_bits("1001101011")) == pytest.approx(0.147232, abs=1e-6)


# --- Obviously non-random input fails ---------------------------------------

@pytest.mark.parametrize("pattern", [
    "1" * 64,          # all ones: monobit fails
    "01" * 32,         # alternates every bit: too many runs
    "0" * 32 + "1" * 32,  # two long blocks: too few runs
])
def test_non_random_fails(pattern):
    result = stats.evaluate(_bits(pattern))
    assert result["pass"] is False


def test_random_bits_usually_pass():
    rng = random.Random(42)
    passes = sum(
        stats.evaluate([rng.getrandbits(1) for _ in range(256)])["pass"]
        for _ in range(200)
    )
    # Two tests at alpha=0.01 -> about 98% should pass.
    assert passes >= 185


# --- Endpoint ---------------------------------------------------------------

@pytest.fixture
def client():
    return create_app().test_client()


def test_stat_test_uses_last_draw(client):
    bits = client.get("/classical-draw?n=128").get_json()["bits"]
    data = client.get("/stat-test?source=classical").get_json()
    assert data["n"] == 128
    assert data["ones"] == sum(bits)
    assert set(data["tests"]) == {"monobit", "runs"}
    assert "placeholder" not in data


def test_stat_test_without_prior_draw(client, monkeypatch):
    monkeypatch.setattr(stats, "_last_batch", {})
    data = client.get("/stat-test?source=quantum").get_json()
    assert isinstance(data["pass"], bool)
    assert data["n"] == 64
