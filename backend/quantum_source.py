"""Quantum random bits — the FIX panel.

Circuit (same for every draw): n qubits, a Hadamard (H) on each one to put it in
an equal superposition of |0> and |1>, then measure. Each qubit collapses to 0 or
1 with probability 1/2. One shot of an n-qubit circuit = one batch of n bits.

Modes (QUANTUM_MODE in .env):
  - "mock":         OS crypto randomness, tagged engine="mock". For frontend dev.
  - "quantumrings": the Quantum Rings SDK, tagged engine="quantumrings".

If the Quantum Rings engine fails we raise QuantumEngineError. We never quietly
fall back to the mock: demoing fake bits as quantum would sink our credibility.
"""
import math
import secrets

from . import config

# Largest circuit the backend accepts. Bigger draws are split into chunks.
QR_MAX_QUBITS = 128
# The statevector has 2**n entries, so keep the "before measurement" view small.
MAX_STATE_QUBITS = 8


class QuantumEngineError(RuntimeError):
    """The Quantum Rings engine is unavailable or a run failed."""


# --- Quantum Rings engine (created once, reused for every request) ----------

_provider = None  # must stay referenced: if it is garbage-collected, runs fail
_backend = None
_qr = None  # the QuantumRingsLib module


def _connect():
    """Create the provider + backend once. Retries on the next call if it failed."""
    global _provider, _backend, _qr
    if _backend is not None:
        return _backend
    if not (config.QR_TOKEN and config.QR_ACCOUNT):
        raise QuantumEngineError(
            "QR_TOKEN and QR_ACCOUNT must be set in .env for QUANTUM_MODE=quantumrings"
        )
    try:
        import QuantumRingsLib as qr

        provider = qr.QuantumRingsProvider(token=config.QR_TOKEN, name=config.QR_ACCOUNT)
        backend = provider.get_backend(config.QR_BACKEND)
    except Exception as err:  # SDK missing, bad credentials, unknown backend...
        raise QuantumEngineError(f"could not connect to Quantum Rings: {err}") from err
    _qr, _provider, _backend = qr, provider, backend
    return backend


def _hadamard_circuit(n: int, measure: bool):
    qreg = _qr.QuantumRegister(n, "q")
    creg = _qr.ClassicalRegister(n, "c")
    qc = _qr.QuantumCircuit(qreg, creg)
    for i in range(n):
        qc.h(i)
    if measure:
        qc.measure(list(range(n)), list(range(n)))
    return qc


def _run(qc):
    try:
        return _backend.run(qc, shots=1).result()
    except Exception as err:
        raise QuantumEngineError(f"Quantum Rings run failed: {err}") from err


def _draw_quantumrings(n: int) -> list[int]:
    _connect()
    bits: list[int] = []
    while len(bits) < n:
        size = min(QR_MAX_QUBITS, n - len(bits))
        memory = _run(_hadamard_circuit(size, measure=True)).get_memory()
        if not memory or len(memory[0]) != size or set(memory[0]) - {"0", "1"}:
            raise QuantumEngineError(f"unexpected result from Quantum Rings: {memory!r}")
        bits.extend(int(b) for b in memory[0])
    return bits


def _statevector_quantumrings(n: int) -> list[complex]:
    _connect()
    return list(_run(_hadamard_circuit(n, measure=False)).get_statevector())


# --- Mock engine ------------------------------------------------------------

def _draw_mock(n: int) -> list[int]:
    return [secrets.randbits(1) for _ in range(n)]


def _statevector_mock(n: int) -> list[complex]:
    # Exact state of H on n qubits: every basis state has amplitude 1/sqrt(2**n).
    amp = 1 / math.sqrt(2**n)
    return [complex(amp, 0)] * (2**n)


# --- Public API -------------------------------------------------------------

def _engine() -> str:
    return "quantumrings" if config.QUANTUM_MODE == "quantumrings" else "mock"


def draw(n: int) -> dict:
    if _engine() == "quantumrings":
        return {"bits": _draw_quantumrings(n), "source": "quantum", "engine": "quantumrings"}
    return {"bits": _draw_mock(n), "source": "quantum", "engine": "mock"}


def state(n: int) -> dict:
    """The qubits' state right before measurement, for the visualizer.

    basis_states: every possible n-bit outcome with its amplitude and probability
                  (probability = |amplitude|^2). Index i of the statevector maps to
                  the bitstring of i, with qubit 0 as the rightmost character.
    qubits:       per-qubit chance of measuring 0 or 1 (for the split bar).
    """
    engine = _engine()
    sv = _statevector_quantumrings(n) if engine == "quantumrings" else _statevector_mock(n)
    if len(sv) != 2**n:
        raise QuantumEngineError(f"expected {2**n} amplitudes, got {len(sv)}")

    basis_states = []
    p1 = [0.0] * n  # chance each qubit reads 1
    for i, amp in enumerate(sv):
        amp = complex(amp)
        prob = abs(amp) ** 2
        basis_states.append({
            "bits": format(i, f"0{n}b"),
            "amplitude": {"re": round(amp.real, 6), "im": round(amp.imag, 6)},
            "probability": round(prob, 6),
        })
        for q in range(n):
            if (i >> q) & 1:
                p1[q] += prob

    total = sum(abs(complex(a)) ** 2 for a in sv)  # ~1.0; divide out float drift
    qubits = []
    for q in range(n):
        one = p1[q] / total if total else 0.5
        qubits.append({"qubit": q, "p0": round(1 - one, 6), "p1": round(one, 6)})

    return {
        "source": "quantum",
        "engine": engine,
        "n": n,
        "circuit": "H on each qubit, before measurement",
        "qubits": qubits,
        "basis_states": basis_states,
    }


# Connect at startup so the first demo click is fast. If it fails here, the error
# is raised again (clearly) on the first request instead of crashing the server.
if _engine() == "quantumrings":
    try:
        _connect()
    except QuantumEngineError:
        pass
