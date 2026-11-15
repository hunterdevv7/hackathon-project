# Quantum branch handoff: DONE

The `quantum` branch's job was to replace the mock quantum source with real Quantum Rings bits, without changing the API the rest of the team builds against. That's finished:

- With `QUANTUM_MODE=quantumrings`, `/quantum-draw` returns bits measured from a Quantum Rings circuit, tagged `"engine": "quantumrings"`. Two calls return different bits.
- The response shape is unchanged: `{"bits": [...], "source": "quantum", "engine": ...}`.
- `pytest` passes in both modes. In mock mode the live tests are skipped; in `quantumrings` mode they all run.

Setup, credentials, the confirmed SDK details and gotchas are all in [SETUP.md](SETUP.md), section 6.

## What was built
| Item from the original task list | Status |
|---|---|
| Answer the open SDK questions (package, Python version, credentials, backend) | Done. See SETUP.md section 6. |
| `_draw_quantumrings(n)`: n qubits, H on each, measure, 1 shot | Done, in [backend/quantum_source.py](backend/quantum_source.py) |
| Provider/backend created once, not per request | Done. Connects at startup and reuses the connection. |
| Clear error on failure, never fall back to the mock | Done. Returns HTTP 503 with a message. |
| Pin `QuantumRingsLib` in `requirements.txt` | Done: `QuantumRingsLib==0.12.2000` |
| Keep the contract fixed | Done. Only new endpoints were added. |
| Live tests (length n, only 0/1, two draws differ) | Done, in [tests/test_quantum.py](tests/test_quantum.py) |
| Stretch: state before measurement for the visualizer | Done: `GET /quantum-state?n=1..8` (see README) |

Differences from the original plan:
- The backend's limit is **128 qubits** per circuit, not 200, so draws over 128 bits are split across several circuits automatically.
- The SDK was tested on **Python 3.13**, not 3.11.

## Still open
- **Statistical check (build step 8):** Done. [backend/stats.py](backend/stats.py) runs the NIST monobit and runs tests on the last batch. Note that the classical PRNG passes these too: its flaw is predictability (replay), not skewed bits.
- **Wi-Fi backup:** probably not needed. The Quantum Rings simulator runs on the local CPU (about 0.1s per draw). If we want one anyway, serve a recorded batch tagged `"engine": "quantumrings-recorded"`.
- **Pitch wording:** Quantum Rings is a simulator running on classical hardware. Present the *mechanism* (superposition → measurement, versus a replayable seed), not "physically random bits".
- **Visualizer:** switch the split bar to read `/quantum-state` instead of hard-coding 50/50.
