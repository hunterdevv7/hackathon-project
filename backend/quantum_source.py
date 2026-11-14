"""Quantum random bits — the FIX panel.

Current state: PLACEHOLDER. In "mock" mode this returns OS crypto randomness so
the frontend can be built now. Every response is tagged engine="mock" so the
placeholder can never be mistaken for the real quantum engine in a demo.

TODO (build-order step 2): implement _draw_quantumrings() with the Quantum Rings
SDK once install/licensing/syntax is confirmed. Planned circuit:
    - n qubits (or 1 qubit x n shots — whichever the platform supports best)
    - Hadamard (H) on each qubit -> equal superposition of |0> and |1>
    - measure -> each qubit collapses to 0 or 1, genuinely undetermined
"""
import secrets

from . import config


def _draw_mock(n: int) -> list[int]:
    return [secrets.randbits(1) for _ in range(n)]


def _draw_quantumrings(n: int) -> list[int]:
    raise NotImplementedError(
        "Quantum Rings engine not wired yet — confirm SDK setup first "
        "(see SETUP.md, 'Quantum Rings setup'). Use QUANTUM_MODE=mock meanwhile."
    )


def draw(n: int) -> dict:
    if config.QUANTUM_MODE == "quantumrings":
        return {"bits": _draw_quantumrings(n), "source": "quantum", "engine": "quantumrings"}
    return {"bits": _draw_mock(n), "source": "quantum", "engine": "mock"}
