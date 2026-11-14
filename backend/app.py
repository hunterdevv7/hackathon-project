"""QuantumFair API — implements the locked contract (see README.md)."""
from flask import Flask, jsonify, request
from flask_cors import CORS

from . import classical_source, config, quantum_source, stats


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


def create_app() -> Flask:
    app = Flask(__name__)
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

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.get("/quantum-draw")
    def quantum_draw():
        result = quantum_source.draw(_parse_n(request.args.get("n")))
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
        return jsonify(quantum_source.state(n))

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
        return jsonify(stats.run(source))

    return app


app = create_app()

if __name__ == "__main__":
    app.run(port=config.PORT, debug=True)
