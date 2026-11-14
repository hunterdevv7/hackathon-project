# QuantumFair: "Bend reality, one qubit at a time"

Our Hack the Nest hackathon project (Quantum Leap track).

A live side-by-side demo. On one side is a classical "random" generator you can crack by replaying its seed. On the other is quantum randomness from the Quantum Rings platform, which can't be reproduced. It's a visualizer and an algorithm demo for the Quantum Leap track.

Setup: see [SETUP.md](SETUP.md).

## API contract (locked)
| Method & path | Response |
|---|---|
| `GET /health` | `{"status": "ok"}` (server is up; doesn't call Quantum Rings) |
| `GET /quantum-draw` | `{"bits": [0,1,...], "source": "quantum", "engine": "mock" \| "quantumrings"}` |
| `GET /classical-draw` | `{"bits": [...], "seed": 1234, "source": "classical"}` |
| `POST /classical-draw/replay` body `{"seed": 1234}` | the same bits as the original draw with that seed |
| `GET /stat-test?source=quantum\|classical` | `{"pass": true, "score": 0.87}` |
| `GET /quantum-state?n=1..8` (default 1) | `{"qubits": [{"qubit": 0, "p0": 0.5, "p1": 0.5}], "basis_states": [{"bits": "0", "amplitude": {"re": 0.707107, "im": 0.0}, "probability": 0.5}, ...], "n": 1, "source": "quantum", "engine": "mock" \| "quantumrings", "circuit": "..."}` |

- Draws accept an optional `?n=` (1–1024, default 64). Replay accepts an optional `"n"` in its body.
- `/quantum-state` is for the visualizer. It returns the qubits' state *before* measurement. The response is a new endpoint and changes nothing in the contract above. In `basis_states`, qubit 0 is the rightmost character of `bits`.
- Errors come back as `{"error": "..."}`: HTTP 400 for bad input, and 503 if the Quantum Rings engine is unavailable. The API never falls back to mock bits.
- Two fields go beyond the contract but don't break it. `engine` stops anyone from demoing the mock as quantum. `placeholder: true` appears on the stat-test until the real test lands.

## Layout
```
backend/   Flask API (app.py) + classical_source, quantum_source, stats, config
frontend/  mocks/*.json fixtures (UI to come)
tests/     pytest API tests
```
