"""Statistical randomness tests that work on bits from any source.

Implements two tests from NIST SP 800-22 using only the standard library:

  * frequency (monobit): are there roughly as many ones as zeros?
  * runs: does the sequence switch between 0 and 1 about as often as a
    random sequence would? This catches patterns like 0101... that are
    exactly 50/50 and so pass the frequency test.

Each test returns a p-value in [0, 1]. A p-value below alpha (0.01 by
default) means the sequence looks non-random.

Important: passing these tests does NOT mean a source is secure. A seeded
PRNG passes them and is still fully predictable from its seed.
"""

import math

MAX_BITS = 100_000


def validate_bits(bits) -> list[int]:
    """Require a non-empty list of 0/1 ints, at most MAX_BITS long."""
    if not isinstance(bits, list):
        raise ValueError("bits must be a list")
    if not bits:
        raise ValueError("bits must not be empty")
    if len(bits) > MAX_BITS:
        raise ValueError(f"bits must have at most {MAX_BITS} items")
    for i, b in enumerate(bits):
        # bool is an int subclass, so reject it explicitly.
        if isinstance(b, bool) or not isinstance(b, int) or b not in (0, 1):
            raise ValueError(f"bits[{i}] must be 0 or 1")
    return bits


def frequency_test(bits) -> float:
    """NIST monobit test.

    S = |ones - zeros| / sqrt(n), p = erfc(S / sqrt(2)).
    Equivalent to a 1-degree-of-freedom chi-square test against 50/50.
    """
    bits = validate_bits(bits)
    n = len(bits)
    ones = sum(bits)
    s_obs = abs(ones - (n - ones)) / math.sqrt(n)
    return math.erfc(s_obs / math.sqrt(2))


def runs_test(bits) -> float:
    """NIST runs test.

    Counts runs (V = 1 + number of switches between 0 and 1) and compares
    with the expected 2 n pi (1 - pi). Returns 0.0 if the frequency
    precondition |pi - 1/2| < 2/sqrt(n) fails, as the NIST spec says.
    """
    bits = validate_bits(bits)
    n = len(bits)
    pi = sum(bits) / n
    if abs(pi - 0.5) >= 2 / math.sqrt(n):
        return 0.0
    switches = sum(1 for a, b in zip(bits, bits[1:]) if a != b)
    v_obs = 1 + switches
    num = abs(v_obs - 2 * n * pi * (1 - pi))
    den = 2 * math.sqrt(2 * n) * pi * (1 - pi)
    return math.erfc(num / den)


def score_bits(bits, alpha: float = 0.01) -> dict:
    """Run every test and summarise.

    Returns {"pass": bool, "score": float, "tests": {name: p_value}}.
    score is the smallest p-value, rounded to 4 decimal places.
    """
    bits = validate_bits(bits)
    raw = {"frequency": frequency_test(bits), "runs": runs_test(bits)}
    worst = min(raw.values())
    return {
        "pass": worst >= alpha,
        "score": round(worst, 4),
        "tests": {name: round(p, 4) for name, p in raw.items()},
    }
