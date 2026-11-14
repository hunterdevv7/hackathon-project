# Setup

## 1. Python environment (Windows)
Use Python 3.11. It's the safe choice until Quantum Rings confirms which versions it supports.

```powershell
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

On macOS/Linux, use `python3.11 -m venv .venv && source .venv/bin/activate` and `cp .env.example .env`.

## 2. Run the API
```powershell
python -m backend.app        # http://localhost:5000
```

## 3. Try every endpoint
```powershell
curl http://localhost:5000/quantum-draw
curl http://localhost:5000/classical-draw              # note the "seed"
curl -X POST http://localhost:5000/classical-draw/replay -H "Content-Type: application/json" -d "{\"seed\": 1234}"
curl "http://localhost:5000/stat-test?source=quantum"
```
Optional: add `?n=128` to a draw to change the batch size (1–1024). Replay also accepts `"n"` in its body.

## 4. Run the tests
```powershell
pytest
```

## 5. Frontend development without the backend
`frontend/mocks/*.json` holds sample responses in exactly the contract's shape.

## 6. Quantum Rings setup (TO CONFIRM)
Status: **not wired yet**. `QUANTUM_MODE=mock` returns placeholder bits tagged `"engine": "mock"`. Setting `QUANTUM_MODE=quantumrings` returns HTTP 501 until this section is done.

Open questions, to answer from the Quantum Rings docs or workshop:
- [ ] Free 200-qubit license registered and activated?
- [ ] Exact pip package name and version (`QuantumRingsLib`?), and supported Python versions
- [ ] How the SDK takes credentials (token + account name? a saved-account call? env vars?)
- [ ] Provider/backend name, plus a minimal working snippet: circuit → `h` → `measure` → run → read counts/memory
- [ ] Batching: one 64-qubit circuit × 1 shot, or 1 qubit × 64 shots (per-shot memory)?

Once these are confirmed, uncomment `QuantumRingsLib` in `requirements.txt`, add credentials to `.env`, and implement `_draw_quantumrings()` in `backend/quantum_source.py`.
