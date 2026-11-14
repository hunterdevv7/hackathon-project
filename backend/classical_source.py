"""Classical "random" bits — the PROBLEM panel.

random.Random is a deterministic PRNG (Mersenne Twister): the same seed always
produces the same bits. That determinism is exactly what the replay "hack"
demonstrates. The seed is deliberately drawn from a tiny 4-digit space, mirroring
real weak-seed exploits — an attacker could brute-force all 10,000 seeds.
"""
import random
import secrets

SEED_SPACE = 10_000


def new_seed() -> int:
    return secrets.randbelow(SEED_SPACE)


def draw(n: int, seed: int | None = None) -> dict:
    if seed is None:
        seed = new_seed()
    rng = random.Random(seed)
    bits = [rng.getrandbits(1) for _ in range(n)]
    return {"bits": bits, "seed": seed, "source": "classical"}
