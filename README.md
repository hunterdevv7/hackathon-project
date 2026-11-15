# QuantumFair: "Bend reality, one qubit at a time"

Our Hack the Nest hackathon project (Quantum Leap track).

A live side-by-side demo. On one side is a classical "random" generator you can crack by replaying its seed. On the other is quantum randomness from the Quantum Rings platform, which can't be reproduced. It's a visualizer and an algorithm demo for the Quantum Leap track.

Setup: see [SETUP.md](SETUP.md). Short version: `python -m backend.app`, then open **http://localhost:5000/**.

## What the page shows
The page in `frontend/` is the pitch and the live demo in one scroll. Every random number on it comes from this API. The browser never makes up bits.

| Section | Problem or fix | What it calls |
|---|---|---|
| The crack: "Pick a seed, pull three times" | Problem: the same seed gives identical reels on three separate requests | `POST /classical-draw/replay` |
| The turn: one qubit, step by step | Fix: H puts a qubit in superposition; measuring it gives one fresh bit | `GET /quantum-draw?n=1` |
| Live demo: one slot machine, switch on **Seeded PRNG** | Problem: **Replay seed** lands on the same reels and reproduces the run bit for bit (64/64) | `GET /classical-draw`, `POST /classical-draw/replay`, `POST /stat-test` |
| Same machine, switch on **Quantum draw** | Fix: the machine turns teal and its marquee reads NO SEED. **Replay seed** has nothing to replay, so fresh qubits land on new reels and match only at chance (~32/64). The θ slider in the right-hand panel shows the randomness comes from superposition: at 0° or 180° the reels repeat. | `GET /quantum-draw?theta=`, `GET /quantum-state?theta=`, `POST /stat-test` |
| The attack | The core claim: the server sees half of your last spin on each side of the switch and tries all 10,000 seeds. It predicts 100% of the PRNG bits and about 50% of the quantum ones. | `POST /attack` |

The source pill on the quantum panel shows which engine answered. It reads **Quantum Rings SDK** for real circuits and **Mock engine** for `QUANTUM_MODE=mock`. If the API is down, the page says so and draws nothing.

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
- Endpoints added for the page. They change nothing above:
  - `GET /engine` returns `{"engine": "mock" | "quantumrings", "ready": true, "error": null, "backend": "scarlet_quantum_rings", "max_batch": 1024, "seed_space": 10000}`. It reports which engine answers and never draws.
  - `?theta=0..180` (degrees) is optional on `/quantum-draw` and `/quantum-state`. The default of 90 is the H circuit; any other value runs RY(θ) on each qubit, so P(0) = cos²(θ/2). Responses also carry `theta` and `circuit`.
  - `POST /stat-test` with body `{"bits": [...]}` runs the same tests on exactly those bits (2–1024 of them).
  - `POST /attack` with body `{"bits": [...]}` (32–1024 bits) is the attacker. It sees the first half, tries every seed, and predicts the second half. It returns `seed` (or `null`), `seeds_matched`, `seeds_tried`, `predicted`, `correct`, `accuracy` and `elapsed_ms`.
  - `GET /` serves the page and `GET /assets/<file>` serves its files.
- Two fields go beyond the contract but don't break it. `engine` stops anyone from demoing the mock as quantum. The stat-test also returns `n`, `ones`, and per-test `tests.{monobit,runs}.{p_value,pass}`. It checks the last batch drawn from that source, or draws a fresh one if there isn't one yet. `score` is the lowest p-value, and the batch passes when every p-value is ≥ 0.01.

## Layout
```
backend/   Flask API (app.py) + classical_source, quantum_source, attack, stats, config
frontend/  index.html + assets/ (the page, served by the API at /) and mocks/*.json fixtures
tests/     pytest API tests
```
