# QuantumFair: "Bend reality, one qubit at a time"

Our Hack the Nest hackathon project (Quantum Leap track).

A live side-by-side demo. On one side is a classical "random" generator you can crack by replaying its seed. On the other is quantum randomness from the Quantum Rings platform, which can't be reproduced. It's a visualizer and an algorithm demo for the Quantum Leap track.

Setup: see [SETUP.md](SETUP.md).

## API contract (locked)
| Method & path | Response |
|---|---|
| `GET /quantum-draw` | `{"bits": [0,1,...], "source": "quantum", "engine": "mock" \| "quantumrings"}` |
| `GET /classical-draw` | `{"bits": [...], "seed": 1234, "source": "classical"}` |
| `POST /classical-draw/replay` body `{"seed": 1234}` | the same bits as the original draw with that seed |
| `GET /stat-test?source=quantum\|classical` | `{"pass": true, "score": 0.87}` |

- Draws accept an optional `?n=` (1–1024, default 64). Replay accepts an optional `"n"` in its body.
- Errors come back as `{"error": "..."}` with HTTP 400. A quantum engine that isn't wired yet returns 501.
- Two fields go beyond the contract but don't break it. `engine` stops anyone from demoing the mock as quantum. `placeholder: true` appears on the stat-test until the real test lands.

## Layout
```
backend/   Flask API (app.py) + classical_source, quantum_source, stats, config
frontend/  mocks/*.json fixtures (UI to come)
tests/     pytest API tests
```
