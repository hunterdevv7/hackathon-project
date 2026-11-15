# Setup

## 1. Python environment (Windows)
Use Python 3.13. That's the version the Quantum Rings SDK (`QuantumRingsLib` 0.12.2000) has been tested on. Other versions may work if pip finds a matching wheel.

```powershell
py -3.13 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

On macOS/Linux, use `python3.13 -m venv .venv && source .venv/bin/activate` and `cp .env.example .env`.

## 2. Run the API
```powershell
python -m backend.app        # http://localhost:5000
```

Terminal demo, no server needed. It shows classical bits being predicted from a brute-forced seed, then quantum bits that can't be predicted, then the stat test:
```powershell
python -m backend.demo       # optional: --n 128
```

## 3. Try every endpoint
```powershell
curl http://localhost:5000/health                      # {"status": "ok"}
curl http://localhost:5000/quantum-draw
curl http://localhost:5000/classical-draw              # note the "seed"
curl -X POST http://localhost:5000/classical-draw/replay -H "Content-Type: application/json" -d "{\"seed\": 1234}"
curl "http://localhost:5000/stat-test?source=quantum"
curl "http://localhost:5000/quantum-state?n=2"         # qubit state before measurement
```
Optional: add `?n=128` to a draw to change the batch size (1–1024). Replay also accepts `"n"` in its body.

`/quantum-state?n=` (1–8, default 1) is for the visualizer. It returns the state of the H circuit *before* measurement:
- `qubits`: each qubit's chance of reading 0 or 1 (`p0`, `p1`), for the 50/50 split bar.
- `basis_states`: every possible outcome with its amplitude (`re`, `im`) and probability. Qubit 0 is the rightmost character of `bits`.

## 4. Run the tests
```powershell
pytest
```
In mock mode the live Quantum Rings tests are skipped. With `QUANTUM_MODE=quantumrings` and credentials set, they run against the real engine.

## 5. Frontend development without the backend
`frontend/mocks/*.json` holds sample responses in exactly the contract's shape.

## 6. Quantum Rings setup
Status: **working**. Set `QUANTUM_MODE=quantumrings` in `.env` for real draws tagged `"engine": "quantumrings"`. Leave it on `mock` if you're only doing frontend work and don't have credentials. The response shape is the same either way.

### Credentials
1. Register for a free account at quantumrings.com and log in. Your license token is on your account page.
2. Put both values in `.env`, which is gitignored. Never commit them or paste them in chat.
   ```
   QUANTUM_MODE=quantumrings
   QR_TOKEN=<your license token>
   QR_ACCOUNT=<the email you registered with>
   ```
3. Restart the API, since `.env` is read at startup.

### What we confirmed
- [x] **Package:** `QuantumRingsLib==0.12.2000`, pinned in `requirements.txt`. It runs together with `quantumrings-cpu` 0.12.2313. Tested on Python 3.13.
- [x] **Credentials:** `QuantumRingsProvider(token=QR_TOKEN, name=QR_ACCOUNT)`.
- [x] **Backend:** `scarlet_quantum_rings`. You can override it with `QR_BACKEND`.
- [x] **Limit:** the backend reports a **128-qubit** maximum per circuit, not 200. Draws above 128 bits are split across several circuits automatically.
- [x] **Batching:** one n-qubit circuit × 1 shot, with the bits read from `result.get_memory()`.
- [x] **Speed:** about 0.1s for a 128-qubit draw. The simulator runs on the local CPU, so the demo doesn't need Wi-Fi.

### Minimal working snippet
```python
import QuantumRingsLib as qr

provider = qr.QuantumRingsProvider(token=TOKEN, name=ACCOUNT)  # keep a reference!
backend = provider.get_backend("scarlet_quantum_rings")

n = 8
qc = qr.QuantumCircuit(qr.QuantumRegister(n, "q"), qr.ClassicalRegister(n, "c"))
for i in range(n):
    qc.h(i)
qc.measure(list(range(n)), list(range(n)))
print(backend.run(qc, shots=1).result().get_memory())  # e.g. ['01110011']
```

### Gotchas
- **Keep the provider object referenced.** If it gets garbage-collected, for example after `QuantumRingsProvider(...).get_backend(...)` in a single line, runs fail with `User is not authenticated`. The app creates it once and keeps it.
- **Create circuits from explicit registers** (`QuantumRegister` + `ClassicalRegister`). `QuantumCircuit(n, n)` prints a deprecation warning.
- **`result.get_probabilities()` rejects the argument values we tried.** We compute probabilities as |amplitude|² from `result.get_statevector()` instead.
- **No silent fallback.** If the engine fails, the API returns HTTP 503 with an error message and never serves mock bits as quantum.
- **It's a simulator.** Quantum Rings models qubits on classical hardware. Pitch the *mechanism* (superposition → measurement, versus a replayable seed), not "physically random bits".
