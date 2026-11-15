"""The attacker. Sees the first half of a run, brute-forces the seed, predicts the rest.

This is the whole argument of the project in one function:
  - Classical bits come from random.Random(seed) with a 4-digit seed. Trying all
    10,000 seeds against the half you saw finds the seed, and the seed gives you
    every hidden bit: 100% correct.
  - Quantum bits come from measuring qubits. No seed reproduces them, so the
    attacker is left guessing: about 50% correct, a coin flip.

The attacker gets no hint about which source the bits came from.
"""
import random
import secrets
import time

from . import classical_source

# With 16+ known bits a wrong seed matches by chance with probability
# 10,000 / 2**16 or less, so ask for at least 32 bits (16 known, 16 hidden).
MIN_BITS = 32


def find_seeds(known: list[int]) -> list[int]:
    """Every seed whose first len(known) bits equal `known`.

    Generates bits exactly like classical_source.draw, one getrandbits(1) at a
    time, and gives up on a seed at its first wrong bit.
    """
    matches = []
    for seed in range(classical_source.SEED_SPACE):
        rng = random.Random(seed)
        for bit in known:
            if rng.getrandbits(1) != bit:
                break
        else:
            matches.append(seed)
    return matches


def run(bits: list[int]) -> dict:
    half = len(bits) // 2
    known, hidden = bits[:half], bits[half:]

    start = time.perf_counter()
    seeds = find_seeds(known)
    elapsed_ms = (time.perf_counter() - start) * 1000

    if seeds:
        seed = seeds[0]
        predicted = classical_source.draw(len(bits), seed=seed)["bits"][half:]
    else:
        seed = None
        predicted = [secrets.randbits(1) for _ in hidden]  # nothing to go on: guess
    correct = sum(p == a for p, a in zip(predicted, hidden))

    return {
        "known_bits": half,
        "hidden_bits": len(hidden),
        "seeds_tried": classical_source.SEED_SPACE,
        "seeds_matched": len(seeds),
        "seed": seed,
        "predicted": predicted,
        "correct": correct,
        "accuracy": round(correct / len(hidden), 4),
        "elapsed_ms": round(elapsed_ms, 1),
    }
