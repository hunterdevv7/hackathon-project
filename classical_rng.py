"""Classical PRNG track for QuantumFair.

Pure logic, no Flask. The point of this module is to show the core weakness
of a pseudo-random number generator: the same seed always produces the same
output, so anyone who knows (or can guess) the seed can predict every bit.

Run it directly for a standalone attack demo:

    python classical_rng.py
"""

import random
import time

BATCH_SIZE = 100


def guessable_seed() -> int:
    """Return the current Unix time in whole seconds.

    This is deliberately guessable. It is the vulnerability being shown:
    an attacker who knows roughly when a draw happened only has to try a
    handful of candidate seeds.
    """
    return int(time.time())


def validate_seed(value) -> int:
    """Accept only a real, non-negative int. Raise ValueError otherwise.

    Rejected on purpose:
      * bool  (True is an int subclass and would silently become seed 1)
      * float (1.0 is not the same type as 1)
      * str   ("1" should not be quietly converted)
      * negative ints, because random.Random seeds with abs(seed), so -5 and
        5 would produce identical output and look like a collision.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"seed must be an integer, got {type(value).__name__}")
    if value < 0:
        raise ValueError("seed must be non-negative")
    return value


def generate_bits(seed: int, n: int = BATCH_SIZE) -> list[int]:
    """Return n bits from a fresh random.Random(seed).

    A new generator is built every call and the global random module is never
    touched, so no other code can shift the stream. That is what makes replay
    exact.
    """
    rng = random.Random(seed)
    return [rng.getrandbits(1) for _ in range(n)]


def classical_draw(seed: int | None = None) -> dict:
    """Draw one batch. Uses a time-based seed when none is given."""
    if seed is None:
        seed = guessable_seed()
    seed = validate_seed(seed)
    return {"bits": generate_bits(seed), "seed": seed, "source": "classical"}


def replay(seed: int) -> list[int]:
    """Reproduce a draw from its seed.

    Uses exactly the same code path as classical_draw so the two can never
    drift apart.
    """
    return generate_bits(validate_seed(seed))


def recover_seed(bits: list[int], now: int | None = None, window: int = 60) -> int | None:
    """Brute force a time-based seed by trying every second in the last `window` seconds.

    Returns the seed that reproduces `bits`, or None if none in the window does.
    """
    if now is None:
        now = guessable_seed()
    for candidate in range(now, now - window - 1, -1):
        if candidate >= 0 and generate_bits(candidate, len(bits)) == bits:
            return candidate
    return None


def _fmt(bits: list[int]) -> str:
    return "".join(str(b) for b in bits)


if __name__ == "__main__":
    print("== Victim draws 100 bits with a time-based seed ==")
    draw = classical_draw()
    print(f"seed: {draw['seed']}")
    print(f"bits: {_fmt(draw['bits'])}")

    print("\n== Attacker replays the known seed ==")
    reproduced = replay(draw["seed"])
    print(f"bits: {_fmt(reproduced)}")
    print(f"MATCH: {reproduced == draw['bits']}")

    print("\n== Attacker does NOT know the seed, only the bits ==")
    print("Trying every second from the last 60 seconds...")
    start = time.perf_counter()
    found = recover_seed(draw["bits"])
    elapsed_ms = (time.perf_counter() - start) * 1000
    if found is None:
        print("No seed found in the window.")
    else:
        print(f"Recovered seed: {found} (in {elapsed_ms:.1f} ms)")
        print(f"Correct: {found == draw['seed']}")
