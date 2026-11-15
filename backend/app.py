"""QuantumFair API — implements the locked contract (see README.md) and serves the
web page from frontend/ at http://localhost:5000/."""
import math
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from . import attack, classical_source, config, quantum_source, stats

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


class BadRequest(Exception):
    pass


def _parse_n(raw) -> int:
    if raw is None:
        return config.BATCH_SIZE
    try:
        n = int(raw)
    except (TypeError, ValueError):
        raise BadRequest("n must be an integer")
    if isinstance(raw, bool) or not 1 <= n <= config.MAX_BATCH:
        raise BadRequest(f"n must be between 1 and {config.MAX_BATCH}")
    return n


def _parse_theta(raw) -> float:
    """Optional rotation in degrees, 0-180. Default 90 = the Hadamard circuit."""
    if raw is None:
        return quantum_source.DEFAULT_THETA
    try:
        theta = float(raw)
    except (TypeError, ValueError):
        raise BadRequest("theta must be a number of degrees")
    if math.isnan(theta) or not 0 <= theta <= 180:
        raise BadRequest("theta must be between 0 and 180")
    return round(theta, 3)


def _parse_bits(raw, min_len: int) -> list[int]:
    if not isinstance(raw, list) or any(b not in (0, 1) or isinstance(b, bool) for b in raw):
        raise BadRequest('body must be JSON like {"bits": [0, 1, 1, ...]}')
    if not min_len <= len(raw) <= config.MAX_BATCH:
        raise BadRequest(f"bits must hold between {min_len} and {config.MAX_BATCH} values")
    return raw


def create_app() -> Flask:
    app = Flask(__name__, static_folder=None)
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0  # always serve the latest page while developing
    CORS(app)

    @app.errorhandler(BadRequest)
    def _bad_request(err):
        return jsonify({"error": str(err)}), 400

    @app.errorhandler(NotImplementedError)
    def _not_implemented(err):
        return jsonify({"error": str(err)}), 501

    @app.errorhandler(quantum_source.QuantumEngineError)
    def _engine_error(err):
        return jsonify({"error": str(err)}), 503

    # --- The web page ------------------------------------------------------

    @app.get("/")
    def index():
        return send_from_directory(FRONTEND_DIR, "index.html")

    @app.get("/assets/<path:name>")
    def assets(name):
        return send_from_directory(FRONTEND_DIR / "assets", name)

    # --- API ---------------------------------------------------------------

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.get("/engine")
    def engine():
        info = quantum_source.status()
        info.update({
            "max_batch": config.MAX_BATCH,
            "seed_space": classical_source.SEED_SPACE,
        })
        return jsonify(info)

    @app.get("/quantum-draw")
    def quantum_draw():
        n = _parse_n(request.args.get("n"))
        result = quantum_source.draw(n, _parse_theta(request.args.get("theta")))
        stats.record("quantum", result["bits"])
        return jsonify(result)

    @app.get("/quantum-state")
    def quantum_state():
        raw = request.args.get("n")
        if raw is None:
            n = 1
        else:
            try:
                n = int(raw)
            except ValueError:
                raise BadRequest("n must be an integer")
        if not 1 <= n <= quantum_source.MAX_STATE_QUBITS:
            raise BadRequest(f"n must be between 1 and {quantum_source.MAX_STATE_QUBITS}")
        return jsonify(quantum_source.state(n, _parse_theta(request.args.get("theta"))))

    @app.get("/classical-draw")
    def classical_draw():
        result = classical_source.draw(_parse_n(request.args.get("n")))
        stats.record("classical", result["bits"])
        return jsonify(result)

    @app.post("/classical-draw/replay")
    def classical_replay():
        body = request.get_json(silent=True) or {}
        seed = body.get("seed")
        if isinstance(seed, bool) or not isinstance(seed, int):
            raise BadRequest('body must be JSON like {"seed": 1234}')
        result = classical_source.draw(_parse_n(body.get("n")), seed=seed)
        return jsonify(result)

    @app.get("/stat-test")
    def stat_test():
        source = request.args.get("source")
        if source not in stats.SOURCES:
            raise BadRequest("source must be 'quantum' or 'classical'")
        result = stats.run(source)
        if result is None:  # nothing drawn yet: test a fresh default-size batch
            module = quantum_source if source == "quantum" else classical_source
            stats.record(source, module.draw(config.BATCH_SIZE)["bits"])
            result = stats.run(source)
        return jsonify(result)

    @app.post("/stat-test")
    def stat_test_bits():
        """Same tests, on exactly the bits in the body (the run the page shows)."""
        body = request.get_json(silent=True) or {}
        return jsonify(stats.evaluate(_parse_bits(body.get("bits"), min_len=2)))

    @app.post("/attack")
    def attack_bits():
        """See the first half of `bits`, brute-force the seed, predict the second half."""
        body = request.get_json(silent=True) or {}
        return jsonify(attack.run(_parse_bits(body.get("bits"), min_len=attack.MIN_BITS)))

    return app


app = create_app()

if __name__ == "__main__":
    print(f" * QuantumFair: open http://localhost:{config.PORT}/  (engine: {quantum_source.status()['engine']})")
    app.run(port=config.PORT, debug=True)
