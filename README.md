# QuantumFair frontend

A single page with two panels. On the left, a classical seeded generator gets "cracked": replaying its seed returns the exact same bits. On the right, a quantum generator on Quantum Rings resists the same trick. The superposition bar is the centerpiece, and a plain-language explainer sits under it.

Plain HTML, CSS and JS. No build step and no dependencies.

## Run it

Either open `index.html` straight from disk, or serve the folder:

```sh
python -m http.server 8000 --directory frontend
# then open http://localhost:8000
```

## Mock vs live backend

Out of the box the page uses mock data (`js/mock.js`) shaped exactly like the API contract. A "Mock data" tag shows in the header whenever mocks are active.

| URL | What it does |
|---|---|
| `index.html` | Mock data, realistic latency (quantum ~1.2-2s, classical ~0.3s) |
| `index.html?latency=fast` | Mock data, near-zero latency |
| `index.html?api=live` | Real backend on the same origin |
| `index.html?api=live&base=http://localhost:5000` | Real backend on another origin |
| `index.html?autorun=1` | Plays the whole story once: draw, replay, two quantum draws. Handy for demo recordings. Combines with the others. |

## API contract the UI expects

```
GET  /quantum-draw                 -> { "bits": [0,1,1,0,...], "source": "quantum" }
GET  /classical-draw               -> { "bits": [...], "seed": 1234, "source": "classical" }
POST /classical-draw/replay        body { "seed": 1234 } -> same bits as the original draw
GET  /stat-test?source=quantum|classical -> { "pass": true, "score": 0.87 }
```

- `bits` must be a non-empty array of `0`/`1`. Any length works; the strip shows up to the first 64.
- `seed` can be a number or a numeric string. Valid seeds are 0 to 4294967295.
- The replay response only needs `bits`.
- Live requests time out after 30 seconds. Failures show inline in the panel with a retry button.

### Note for the backend team: CORS

If the backend serves this folder itself, nothing extra is needed. If the page runs on a different origin, for example `python -m http.server` on port 8000 with the API on 5000, the API must allow it:

- Flask: `pip install flask-cors`, then `CORS(app)`.
- FastAPI: add `CORSMiddleware` with `allow_origins=["*"]` for the demo.

## Files

| File | Role |
|---|---|
| `index.html` | Markup for both panels, with the two icons inlined |
| `styles.css` | Design tokens, layout, visualizer motion, reduced-motion fallbacks |
| `js/mock.js` | Mock endpoints. The mock "quantum" bits come from the browser's crypto generator and are only a placeholder. |
| `js/api.js` | Mock or live switch. The only place that knows about URLs. |
| `js/visualizer.js` | Superposition bar and per-bit collapse strip |
| `js/app.js` | Panels, logs, loaders, seed validation, stat badges |
| `assets/*.svg` | Source copies of the two icons, generated with Higgsfield and cleaned up |

## Design rules this follows

- **Color 60/30/10:** paper neutrals, graphite ink, and one accent ("Cherenkov blue" `#2f5bff`). The accent is used only for Run Draw, the visualizer and focus rings. Brick red is used only for errors and Fail.
- **Type:** IBM Plex Sans and Mono, weights 400 and 600. Sizes 14/16/20/28/36px, each with its own line height.
- **Spacing:** 4, 8, 12, 16, 24, 32, 48 and 64px only.
- **Motion:** transform and opacity only, 150-250ms. The collapse is the one expressive animation. `prefers-reduced-motion` turns it into an instant swap.
- **Loaders:** nothing under 100ms, an inline spinner after 100ms, and skeletons after 1s.
- **Layout:** works from 375px to 1280px with no horizontal scroll.
