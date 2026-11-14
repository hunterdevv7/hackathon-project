# Quantum branch handoff

Your job is to replace the mock quantum source with real bits from Quantum Rings, without changing the API the rest of the team builds against. Right now `/quantum-draw` returns ordinary computer-generated random bits tagged `"engine": "mock"`. When you're done, it returns real measured qubits tagged `"engine": "quantumrings"`.

## 1. Get set up (about 15 minutes)
```powershell
git clone https://github.com/hunterdevv7/hackathon-project.git
cd hackathon-project
git switch quantum
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
pytest        # should show 14 passed
```
[SETUP.md](SETUP.md) has the full steps and curl examples for every endpoint.

## 2. Answer the open questions in SETUP.md, section 6
Do this first. Wiring up Quantum Rings is the riskiest part of the project.
- Register for the free 200-qubit license and get your token.
- Find the exact pip package name and version, and check that it works on Python 3.11.
- Find out how it takes credentials, then add those variables to `.env.example` and read them in [backend/config.py](backend/config.py). Real credentials go in `.env` only, which is gitignored. Never commit them.
- Get a minimal example working on its own before touching the app. The SDK probably looks roughly like `QuantumRingsProvider(token=..., name=...)` → `get_backend(...)` → `backend.run(qc, shots=...)`, but that's unconfirmed. Check it against their docs or workshop.

## 3. Implement the real draw
Fill in `_draw_quantumrings(n)` in [backend/quantum_source.py](backend/quantum_source.py):
- Build a circuit with `n` qubits, put each in superposition with a Hadamard (`H`) gate, measure all of them, and run 1 shot. That gives one batch of `n` bits per call.
  - If the platform only returns totals rather than each shot's result, 1 qubit × `n` shots won't work, so stick with `n` qubits × 1 shot.
- Return a plain `list[int]` of exactly `n` values, each 0 or 1. Bit order doesn't matter for randomness.
- Create the provider and backend once when the module loads, not on every request, so the live demo stays fast.
- If the engine fails, raise a clear error. Never quietly fall back to the mock, because demoing fake bits as quantum is the one thing that would sink credibility with the judges.
- Uncomment `QuantumRingsLib` in `requirements.txt`, pinned to the version you tested.

## 4. Keep the contract fixed
The response must stay `{"bits": [...], "source": "quantum", "engine": "quantumrings"}`. The `Classical` and `visualizer` branches build against this shape, using the mocks in `frontend/mocks/`. If you need to add something, add new fields and don't rename existing ones. Tell the team before you do.

## 5. Tests
- All existing tests must still pass in mock mode.
- Add a live test that runs only when `QUANTUM_MODE=quantumrings` and credentials are present, and is skipped otherwise. It should check that the batch has length `n`, that the values are only 0 or 1, and that two draws differ.

## 6. Stretch goals, once the core works
- **Statistical check (build step 8):** replace the placeholder in [backend/stats.py](backend/stats.py) with a real frequency or chi-square test.
- **Help the visualizer:** add an endpoint or field that describes the qubit's state before measurement (50/50, amplitudes 1/√2). The visualizer can then draw the split bar from real data instead of hardcoding it.
- **Wi-Fi backup for the demo:** keep a recorded batch from a real run, served with a label like `"engine": "quantumrings-recorded"`, so nobody mistakes it for a live run.

## Done when
With `QUANTUM_MODE=quantumrings`, two calls to `/quantum-draw` return different real bits tagged `"engine": "quantumrings"`. `pytest` passes, and the changes are pushed to `quantum` with a pull request opened to `main`.
