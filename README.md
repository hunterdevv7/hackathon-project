# QuantumFair: "Bend reality, one qubit at a time"

**Live demo: http://144.202.9.26/**

Our Hack the Nest hackathon project (Quantum Leap track) by **Adrian Spencer, Adriel Reyes, Hasset Admasu and Hunter Burk**.

Most "random" numbers in software come from a formula with a starting value, the seed. Learn the seed and you can predict every number the formula will ever produce. That is how slot machines, SSL keys and Bitcoin wallets have been broken for real. A measured qubit has no seed: there is nothing to steal.

QuantumFair is one slot machine with a switch. On **Seeded PRNG** it runs on Python's `random.Random` with a 4-digit seed, and you can replay the seed to reproduce a spin bit for bit. On **Quantum draw** every bit comes from measuring a qubit through the [Quantum Rings](https://www.quantumrings.com/) SDK, and replaying matches only at chance. Then an attacker tries to predict both. One of them breaks.

## Try it in two minutes
1. Open the live demo and scroll: the crack (the 2017 slot-machine exploit), the stakes, the turn.
2. On the machine, pull with **Seeded PRNG**, then **Replay seed**: 64 of 64 bits identical.
3. Flip to **Quantum draw** (marquee reads NO SEED), pull, replay: about 32 of 64 match, pure chance.
4. Drag the **θ slider** to 0° or 180°: no superposition, no randomness, the reels repeat.
5. Run **the attack**: it sees half of your last spin, tries all 10,000 seeds, and predicts the other half. 100% right on the PRNG, about 50% on the quantum bits.

The source pill on the quantum panel shows which engine answered. It reads **Quantum Rings SDK** for real circuits and **Dev mock (not quantum)** only when a developer runs with `QUANTUM_MODE=mock`. If the engine is down the page says so and draws nothing; the API never passes off fake bits as quantum.

## How it works

**The quantum side.** Each bit is one qubit. A Hadamard gate puts it in an equal superposition, (|0⟩ + |1⟩)/√2, so measuring it gives 0 or 1 with probability ½. An n-bit draw is one n-qubit circuit measured once: nothing collected in advance, nothing reused. The θ slider swaps H for RY(θ), where P(0) = cos²(θ/2): 90° is the fair coin, 0° and 180° have no superposition and no randomness. The visualizer reads the circuit's statevector before measurement to show the amplitudes.

**The classical side.** `random.Random(seed)` (Mersenne Twister) with a seed from 0 to 9,999, on purpose: weak seeds are the mistake behind the real exploits the page cites. The whole stream carries only about 13 bits of unpredictability however many bits you pull.

**The attack.** Given a run of bits, it takes the first half as "seen", generates bits for every one of the 10,000 seeds, keeps the seeds that match, and predicts the hidden half. With 16 or more seen bits a wrong seed matches by accident less than 10,000/2¹⁶ of the time, so runs are 32 bits or longer.

**The statistics.** `/stat-test` runs two NIST SP 800-22 tests, monobit (balance of 1s and 0s) and runs (how often the bits flip), and passes a batch when every p-value is ≥ 0.01. Both sources pass. That is the point: statistics can't see a seed. Only the attack can.

**Honest framing.** Quantum Rings simulates the circuit on the server's CPU, so the bits come from a simulator sampling quantum probabilities. What the demo shows is the mechanism, superposition then measurement versus a replayable seed. The same circuit on quantum hardware would give physically random bits; we don't claim our server does.

## Run it yourself
```bash
python -m venv .venv && .venv/Scripts/activate      # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                                 # then fill in QR_TOKEN and QR_ACCOUNT
python -m backend.app                                # open http://localhost:5000/
pytest -q                                            # 64 tests; the live Quantum Rings ones skip without credentials
```
Credentials come from a free account at quantumrings.com (the license token and the email you registered with). No credentials yet? Set `QUANTUM_MODE=mock` in `.env` for frontend work; the page will label the bits as mock. Full setup notes, confirmed SDK details and gotchas are in [SETUP.md](SETUP.md).

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
- `/quantum-state` is for the visualizer. It returns the qubits' state *before* measurement. In `basis_states`, qubit 0 is the rightmost character of `bits`.
- Errors come back as `{"error": "..."}`: HTTP 400 for bad input, 404/405 for unknown routes or methods, 413 for bodies over 64 KB, 429 when a client exceeds the rate limit, and 503 if the Quantum Rings engine is unavailable. The API never falls back to mock bits and never returns an HTML error page or a stack trace.
- Cross-origin browser calls are refused unless `CORS_ORIGINS` is set in `.env` (see `.env.example`). The served page is same-origin, so production doesn't need it.
- Endpoints added for the page. They change nothing above:
  - `GET /engine` returns `{"engine": "mock" | "quantumrings", "ready": true, "error": null, "backend": "scarlet_quantum_rings", "max_batch": 1024, "seed_space": 10000}`. It reports which engine answers and never draws.
  - `?theta=0..180` (degrees) is optional on `/quantum-draw` and `/quantum-state`. The default of 90 is the H circuit; any other value runs RY(θ) on each qubit, so P(0) = cos²(θ/2). Responses also carry `theta` and `circuit`.
  - `POST /stat-test` with body `{"bits": [...]}` runs the same tests on exactly those bits (2–1024 of them).
  - `POST /attack` with body `{"bits": [...]}` (32–1024 bits) is the attacker. It sees the first half, tries every seed, and predicts the second half. It returns `seed` (or `null`), `seeds_matched`, `seeds_tried`, `predicted`, `correct`, `accuracy` and `elapsed_ms`.
  - `GET /` serves the page and `GET /assets/<file>` serves its files.
- Two fields go beyond the contract but don't break it. `engine` stops anyone from demoing the mock as quantum. The stat-test also returns `n`, `ones`, and per-test `tests.{monobit,runs}.{p_value,pass}`. It checks the last batch drawn from that source, or draws a fresh one if there isn't one yet. `score` is the lowest p-value.

## Deployment and security
The live demo runs on one Vultr instance (Ubuntu 24.04, 1 vCPU): nginx on port 80 in front of gunicorn running the Flask app, with the Quantum Rings simulator on the instance's CPU. `./deploy/vultr.sh` creates the server through the Vultr API and `./deploy/deploy.sh <ip> --with-env` deploys this working copy; see [DEPLOY.md](DEPLOY.md).

Every deploy also hardens the box: key-only SSH with fail2ban, automatic security updates, the app running as an unprivileged user in a systemd sandbox on a read-only filesystem, and nginx with per-IP rate limits, a strict Content-Security-Policy and the usual security headers. CI runs the tests on Python 3.12 and 3.13, audits dependencies for known vulnerabilities, and fails if a credentials file is ever committed. Details and what to do if a credential leaks: [SECURITY.md](SECURITY.md).

## Layout
```
backend/   Flask API (app.py) + classical_source, quantum_source, attack, stats, config
frontend/  index.html + assets/ (the page, served by the API at /) and mocks/*.json fixtures
tests/     pytest: API contract, demo flows, quantum engine (live tests skip without credentials), stats, security
deploy/    Vultr scripts (vultr.sh, deploy.sh, setup.sh), systemd unit, nginx site
.github/   CI workflow and Dependabot
```

## Sources cited on the page
- WIRED (2017), "Russians Engineer a Brilliant Slot Machine Cheat, and Casinos Have No Fix"
- Debian Security Advisory DSA-1571 / CVE-2008-0166, predictable OpenSSL keys
- Bitcoin.org (August 2013), Android SecureRandom wallet vulnerability
- Goldberg and Wagner, Dr. Dobb's Journal (1996), Netscape SSL randomness
- ID Quantique, QRNG for Loterie Romande draws
- NIST SP 800-22, statistical test suite for random number generators
