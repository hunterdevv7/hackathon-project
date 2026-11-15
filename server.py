"""Flask API for the QuantumFair classical track.

Endpoints
---------
GET  /classical-draw                 -> {"bits", "seed", "source": "classical"}
     optional ?seed=<non-negative int> overrides the time-based seed
POST /classical-draw/replay          body {"seed": 1234} -> same shape as a draw
GET  /stat-test?source=classical|quantum -> {"pass", "score", "tests"}
POST /stat-test                      body {"bits": [...]} -> {"pass", "score", "tests"}

Quantum hookup (for the quantum teammate)
-----------------------------------------
    import server
    server.register_source("quantum", my_function)  # my_function() -> list of 0/1

Until a quantum source is registered, GET /stat-test?source=quantum returns 503.
"""

import re

from flask import Flask, jsonify, request

from classical_rng import classical_draw, replay, validate_seed
from randomness_tests import score_bits, validate_bits

app = Flask(__name__)

# Most recent classical draw, kept in memory so /stat-test can score it.
_last_draw: dict | None = None

# External bit sources, e.g. {"quantum": fn}. fn() must return a list of bits.
_sources: dict = {}

_DIGITS = re.compile(r"[0-9]+")


def register_source(name: str, fn) -> None:
    """Register a callable that returns a list of 0/1 bits."""
    if name == "classical":
        raise ValueError("'classical' is built in and cannot be replaced")
    if not callable(fn):
        raise ValueError("fn must be callable")
    _sources[name] = fn


def unregister_source(name: str) -> None:
    _sources.pop(name, None)


def _error(message: str, status: int):
    return jsonify({"error": message}), status


@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


@app.get("/classical-draw")
def get_classical_draw():
    global _last_draw
    raw_seed = request.args.get("seed")
    seed = None
    if raw_seed is not None:
        # Query strings are always text, so parse strictly: digits only.
        if not _DIGITS.fullmatch(raw_seed):
            return _error("seed must be a non-negative integer", 400)
        seed = int(raw_seed)
    draw = classical_draw(seed)
    _last_draw = draw
    return jsonify(draw)


@app.post("/classical-draw/replay")
def post_replay():
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or "seed" not in body:
        return _error("body must be JSON like {\"seed\": 1234}", 400)
    try:
        seed = validate_seed(body["seed"])
    except ValueError as exc:
        return _error(str(exc), 400)
    return jsonify({"bits": replay(seed), "seed": seed, "source": "classical"})


@app.get("/stat-test")
def get_stat_test():
    global _last_draw
    source = request.args.get("source", "classical")

    if source == "classical":
        if _last_draw is None:
            _last_draw = classical_draw()
        return jsonify(score_bits(_last_draw["bits"]))

    if source == "quantum":
        fn = _sources.get("quantum")
        if fn is None:
            return _error("quantum source not connected", 503)
        try:
            bits = validate_bits(fn())
        except ValueError as exc:
            return _error(f"quantum source returned invalid bits: {exc}", 502)
        except Exception as exc:  # the teammate's code failed, not ours
            return _error(f"quantum source failed: {exc}", 502)
        return jsonify(score_bits(bits))

    return _error("source must be 'classical' or 'quantum'", 400)


@app.post("/stat-test")
def post_stat_test():
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or "bits" not in body:
        return _error("body must be JSON like {\"bits\": [0, 1, ...]}", 400)
    try:
        return jsonify(score_bits(body["bits"]))
    except ValueError as exc:
        return _error(str(exc), 400)


if __name__ == "__main__":
    app.run(port=5000, debug=True)
