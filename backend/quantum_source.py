"""Quantum random bits — the FIX panel.

Default circuit: n qubits, a Hadamard (H) on each one to put it in an equal
superposition of |0> and |1>, then measure. Each qubit collapses to 0 or 1 with
probability 1/2. One shot of an n-qubit circuit = one batch of n bits.

Optional theta (degrees, 0-180) for the visualizer's slider: RY(theta) on each
qubit instead of H, so P(0) = cos^2(theta/2). theta=90 is the H circuit (same
probabilities), 0 is plain |0> and 180 is plain |1>: no superposition, no randomness.

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
# 90 degrees = the Hadamard circuit, the one the randomness claim is about.
DEFAULT_THETA = 90.0


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


def _circuit(n: int, measure: bool, theta: float = DEFAULT_THETA):
    qreg = _qr.QuantumRegister(n, "q")
    creg = _qr.ClassicalRegister(n, "c")
    qc = _qr.QuantumCircuit(qreg, creg)
    for i in range(n):
        if theta == DEFAULT_THETA:
            qc.h(i)
        elif theta != 0:
            qc.ry(math.radians(theta), i)
        # theta == 0: no gate, the qubit stays in |0>
    if measure:
        qc.measure(list(range(n)), list(range(n)))
    return qc


def _run(qc):
    try:
        return _backend.run(qc, shots=1).result()
    except Exception as err:
        raise QuantumEngineError(f"Quantum Rings run failed: {err}") from err


def _draw_quantumrings(n: int, theta: float) -> list[int]:
    _connect()
    bits: list[int] = []
    while len(bits) < n:
        size = min(QR_MAX_QUBITS, n - len(bits))
        memory = _run(_circuit(size, measure=True, theta=theta)).get_memory()
        if not memory or len(memory[0]) != size or set(memory[0]) - {"0", "1"}:
            raise QuantumEngineError(f"unexpected result from Quantum Rings: {memory!r}")
        bits.extend(int(b) for b in memory[0])
    return bits


def _statevector_quantumrings(n: int, theta: float) -> list[complex]:
    _connect()
    return list(_run(_circuit(n, measure=False, theta=theta)).get_statevector())


# --- Mock engine ------------------------------------------------------------

def _p1(theta: float) -> float:
    """Chance a qubit prepared with RY(theta) measures 1: sin^2(theta/2)."""
    return math.sin(math.radians(theta) / 2) ** 2


def _draw_mock(n: int, theta: float) -> list[int]:
    if theta == DEFAULT_THETA:
        return [secrets.randbits(1) for _ in range(n)]
    scale = 1 << 53
    cut = round(_p1(theta) * scale)
    return [1 if secrets.randbelow(scale) < cut else 0 for _ in range(n)]


def _statevector_mock(n: int, theta: float) -> list[complex]:
    # Exact product state of RY(theta) (or H) on n qubits. For H every basis state
    # has amplitude 1/sqrt(2**n).
    a0 = math.cos(math.radians(theta) / 2)
    a1 = math.sin(math.radians(theta) / 2)
    out = []
    for i in range(2**n):
        amp = 1.0
        for q in range(n):
            amp *= a1 if (i >> q) & 1 else a0
        out.append(complex(amp, 0))
    return out


# --- Public API -------------------------------------------------------------

def _engine() -> str:
    return "quantumrings" if config.QUANTUM_MODE == "quantumrings" else "mock"


def describe(theta: float) -> str:
    if theta == DEFAULT_THETA:
        return "H on each qubit"
    if theta == 0:
        return "no gate on each qubit (stays |0>)"
    return f"RY({theta:g} deg) on each qubit"


def status() -> dict:
    """Which engine answers /quantum-draw, and whether it is ready. Never draws."""
    engine = _engine()
    info = {"engine": engine, "ready": True, "error": None, "backend": None}
    if engine == "quantumrings":
        info["backend"] = config.QR_BACKEND
        try:
            _connect()
        except QuantumEngineError as err:
            info["ready"], info["error"] = False, str(err)
    return info


def draw(n: int, theta: float = DEFAULT_THETA) -> dict:
    engine = _engine()
    if engine == "quantumrings":
        bits = _draw_quantumrings(n, theta)
    else:
        bits = _draw_mock(n, theta)
    return {
        "bits": bits,
        "source": "quantum",
        "engine": engine,
        "theta": theta,
        "circuit": describe(theta) + ", measure, 1 shot",
    }


def state(n: int, theta: float = DEFAULT_THETA) -> dict:
    """The qubits' state right before measurement, for the visualizer.

    basis_states: every possible n-bit outcome with its amplitude and probability
                  (probability = |amplitude|^2). Index i of the statevector maps to
                  the bitstring of i, with qubit 0 as the rightmost character.
    qubits:       per-qubit chance of measuring 0 or 1 (for the split bar).
    """
    engine = _engine()
    if engine == "quantumrings":
        sv = _statevector_quantumrings(n, theta)
    else:
        sv = _statevector_mock(n, theta)
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
        "theta": theta,
        "circuit": describe(theta) + ", before measurement",
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
