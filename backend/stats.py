"""Statistical randomness check — STUB.

Keeps the most recent batch from each source in memory so the real test
(build-order step 8: frequency / chi-square) has data to work on. For now it
returns a fixed placeholder result in the contract shape.
"""
SOURCES = ("quantum", "classical")

_last_batch: dict[str, list[int]] = {}


def record(source: str, bits: list[int]) -> None:
    _last_batch[source] = bits


def last_batch(source: str) -> list[int] | None:
    return _last_batch.get(source)


def run(source: str) -> dict:
    # TODO (step 8): real chi-square/monobit test on last_batch(source)
    return {"pass": True, "score": 0.87, "placeholder": True}
