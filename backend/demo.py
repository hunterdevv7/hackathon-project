#myenv/bin/python -m backend.demo


"""Terminal demo of the whole backend, no server needed.

    python -m backend.demo          # 64 bits: attacker sees 32, predicts 32
    python -m backend.demo --n 128

1. Draw classical bits (weak 4-digit seed).
2. "Attacker" sees only the first half, brute-forces the seed, predicts the rest.
3. Draw quantum bits and try the same attack. No seed fits, so it can only guess.
4. Run the stat test on both.
"""
import argparse
import secrets
import time

from . import classical_source, config, quantum_source, stats

GREEN, RED, DIM, BOLD, RESET = "\033[32m", "\033[31m", "\033[2m", "\033[1m", "\033[0m"


def bitstr(bits: list[int]) -> str:
    return "".join(map(str, bits))


def as_number(bits: list[int]) -> int:
    return int(bitstr(bits), 2) if bits else 0


def header(title: str) -> None:
    print(f"\n{BOLD}=== {title} ==={RESET}")


def find_seeds(known: list[int]) -> list[int]:
    """Try every possible seed; keep those that reproduce the known bits."""
    return [
        seed for seed in range(classical_source.SEED_SPACE)
        if classical_source.draw(len(known), seed=seed)["bits"] == known
    ]


def show_prediction(predicted: list[int], actual: list[int]) -> None:
    marks = "".join(
        f"{GREEN}{p}{RESET}" if p == a else f"{RED}{p}{RESET}"
        for p, a in zip(predicted, actual)
    )
    correct = sum(p == a for p, a in zip(predicted, actual))
    total = len(actual)
    color = GREEN if correct == total else RED
    print(f"  predicted: {marks}   = {as_number(predicted)}")
    print(f"  actual:    {bitstr(actual)}   = {as_number(actual)}")
    print(f"  {color}{correct}/{total} correct ({correct / total:.0%}){RESET}")


def attack(bits: list[int]) -> None:
    half = len(bits) // 2
    known, hidden = bits[:half], bits[half:]
    print(f"  attacker sees first {half} bits: {bitstr(known)}")
    start = time.perf_counter()
    seeds = find_seeds(known)
    elapsed = time.perf_counter() - start
    print(f"  tried all {classical_source.SEED_SPACE:,} seeds in {elapsed:.2f}s"
          f" -> {len(seeds)} match{'es' if len(seeds) != 1 else ''}")

    if seeds:
        seed = seeds[0]
        print(f"  {GREEN}recovered seed: {seed}{RESET} -> predicting the hidden {len(hidden)} bits")
        predicted = classical_source.draw(len(bits), seed=seed)["bits"][half:]
    else:
        print(f"  {RED}no seed fits{RESET} -> attacker can only guess the hidden {len(hidden)} bits")
        predicted = [secrets.randbits(1) for _ in hidden]
    show_prediction(predicted, hidden)


def show_stats(source: str, bits: list[int]) -> None:
    stats.record(source, bits)
    r = stats.run(source)
    verdict = f"{GREEN}PASS{RESET}" if r["pass"] else f"{RED}FAIL{RESET}"
    tests = ", ".join(f"{name} p={t['p_value']:.3f}" for name, t in r["tests"].items())
    print(f"  {source:<9} {verdict}  ({r['ones']}/{r['n']} ones; {tests})")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--n", type=int, default=config.BATCH_SIZE, help="bits per draw (default 64)")
    args = parser.parse_args()
    if not 2 <= args.n <= config.MAX_BATCH:
        parser.error(f"--n must be between 2 and {config.MAX_BATCH}")

    header("1. Classical draw (Python PRNG, 4-digit seed)")
    classical = classical_source.draw(args.n)
    print(f"  bits:   {bitstr(classical['bits'])}")
    print(f"  number: {as_number(classical['bits'])}")
    print(f"  {DIM}secret seed: {classical['seed']}{RESET}")

    header("2. Attack the classical bits")
    attack(classical["bits"])

    header("3. Quantum draw + same attack")
    try:
        quantum = quantum_source.draw(args.n)
    except quantum_source.QuantumEngineError as err:
        print(f"  {RED}quantum engine error: {err}{RESET}")
        quantum = None
    if quantum:
        print(f"  engine: {quantum['engine']}"
              + (f"  {DIM}(mock = OS randomness, not Quantum Rings){RESET}" if quantum["engine"] == "mock" else ""))
        print(f"  bits:   {bitstr(quantum['bits'])}")
        print(f"  number: {as_number(quantum['bits'])}")
        attack(quantum["bits"])

    header("4. Stat test (NIST monobit + runs)")
    show_stats("classical", classical["bits"])
    if quantum:
        show_stats("quantum", quantum["bits"])
    print(f"  {DIM}Both usually pass: the classical flaw is predictability, not skewed bits.{RESET}")


if __name__ == "__main__":
    main()
