"""Statistical randomness check on the most recent batch from each source.

Two tests from NIST SP 800-22 (the standard randomness test suite):
  - monobit (frequency): are there roughly as many 1s as 0s?
  - runs:                does the sequence flip between 0 and 1 about as often
                         as a fair coin would? (catches "0101..." or "000111")

Each test gives a p-value: the chance a truly random sequence would look at least
this lopsided. A batch passes if every p-value is >= ALPHA (NIST uses 0.01).
`score` is the smallest p-value. For random data p-values are spread evenly over
0..1, so 0.2 is not "worse" than 0.9. Only falling below ALPHA means failure.

Important for the pitch: Python's PRNG passes these tests too. Its weakness is
that the seed makes it predictable, not that its bits look skewed. That is what the
replay demo shows.
"""
import math

SOURCES = ("quantum", "classical")
ALPHA = 0.01

_last_batch: dict[str, list[int]] = {}


def record(source: str, bits: list[int]) -> None:
    _last_batch[source] = bits


def last_batch(source: str) -> list[int] | None:
    return _last_batch.get(source)


def monobit(bits: list[int]) -> float:
    """NIST 2.1: frequency test. Returns the p-value."""
    n = len(bits)
    s = sum(1 if b else -1 for b in bits)  # +1 for each 1, -1 for each 0
    return math.erfc(abs(s) / math.sqrt(n) / math.sqrt(2))


def runs(bits: list[int]) -> float:
    """NIST 2.3: runs test. Returns the p-value."""
    n = len(bits)
    pi = sum(bits) / n
    # Prerequisite: if the 0/1 balance is already far off, the test is not
    # applicable and NIST says to report p = 0.
    if abs(pi - 0.5) >= 2 / math.sqrt(n) or pi in (0, 1):
        return 0.0  # pi of 0 or 1 (all one value) would also divide by zero below
    v_obs = 1 + sum(bits[i] != bits[i + 1] for i in range(n - 1))
    expected = 2 * n * pi * (1 - pi)
    return math.erfc(abs(v_obs - expected) / (2 * math.sqrt(2 * n) * pi * (1 - pi)))


def evaluate(bits: list[int]) -> dict:
    """Run every test on `bits` and return the API response."""
    p_values = {"monobit": monobit(bits), "runs": runs(bits)}
    return {
        "pass": all(p >= ALPHA for p in p_values.values()),
        "score": round(min(p_values.values()), 6),
        "n": len(bits),
        "ones": sum(bits),
        "tests": {
            name: {"p_value": round(p, 6), "pass": p >= ALPHA}
            for name, p in p_values.items()
        },
    }


def run(source: str) -> dict | None:
    """Test the last batch drawn from `source`. None if nothing was drawn yet."""
    bits = last_batch(source)
    return evaluate(bits) if bits else None
