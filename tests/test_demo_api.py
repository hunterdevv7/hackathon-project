"""Endpoints the web page uses beyond the original contract: /engine, theta,
POST /stat-test, /attack, and the page itself."""
import pytest

from backend import attack, classical_source, config, quantum_source
from backend.app import create_app


@pytest.fixture
def client():
    return create_app().test_client()


@pytest.fixture
def mock_mode(monkeypatch):
    monkeypatch.setattr(config, "QUANTUM_MODE", "mock")


# --- The page ----------------------------------------------------------------

def test_serves_page_and_assets(client):
    page = client.get("/")
    assert page.status_code == 200 and b"QuantumFair" in page.data
    for name in ("app.js", "styles.css"):
        assert client.get(f"/assets/{name}").status_code == 200


def test_unknown_asset_is_404(client):
    assert client.get("/assets/nope.js").status_code == 404


# --- /engine ------------------------------------------------------------------

def test_engine_mock(client, mock_mode):
    data = client.get("/engine").get_json()
    assert data["engine"] == "mock" and data["ready"] is True
    assert data["max_batch"] == config.MAX_BATCH
    assert data["seed_space"] == classical_source.SEED_SPACE


def test_engine_reports_quantumrings_failure(client, monkeypatch):
    monkeypatch.setattr(config, "QUANTUM_MODE", "quantumrings")
    monkeypatch.setattr(config, "QR_TOKEN", "")
    monkeypatch.setattr(quantum_source, "_backend", None)
    data = client.get("/engine").get_json()
    assert data["engine"] == "quantumrings" and data["ready"] is False
    assert "QR_TOKEN" in data["error"]


# --- theta --------------------------------------------------------------------

def test_default_theta_is_hadamard(client, mock_mode):
    data = client.get("/quantum-draw?n=8").get_json()
    assert data["theta"] == 90 and data["circuit"].startswith("H on each qubit")


@pytest.mark.parametrize("theta, value", [("0", 0), ("180", 1)])
def test_poles_are_not_random(client, mock_mode, theta, value):
    bits = client.get(f"/quantum-draw?n=64&theta={theta}").get_json()["bits"]
    assert bits == [value] * 64


def test_theta_60_is_biased_toward_zero(client, mock_mode):
    bits = client.get("/quantum-draw?n=1024&theta=60").get_json()["bits"]
    assert 0.65 < bits.count(0) / 1024 < 0.85  # P(0) = cos^2(30 deg) = 0.75


def test_state_follows_theta(client, mock_mode):
    q = client.get("/quantum-state?theta=60").get_json()["qubits"][0]
    assert q["p0"] == pytest.approx(0.75, abs=1e-6)
    assert q["p1"] == pytest.approx(0.25, abs=1e-6)


@pytest.mark.parametrize("theta", ["-1", "181", "abc", "nan"])
def test_bad_theta(client, theta):
    assert client.get(f"/quantum-draw?theta={theta}").status_code == 400
    assert client.get(f"/quantum-state?theta={theta}").status_code == 400


# --- POST /stat-test ------------------------------------------------------------

def test_stat_test_on_given_bits(client):
    data = client.post("/stat-test", json={"bits": [0, 1] * 50}).get_json()
    assert data["n"] == 100 and data["ones"] == 50
    assert data["tests"]["runs"]["pass"] is False  # 0101... flips far too often


def test_stat_test_all_same_bits_does_not_crash(client):
    data = client.post("/stat-test", json={"bits": [1, 1, 1, 1]}).get_json()
    assert data["pass"] is False


@pytest.mark.parametrize("body", [{}, {"bits": "0101"}, {"bits": [0, 2]}, {"bits": [True, False]}, {"bits": [1]}])
def test_stat_test_rejects_bad_bits(client, body):
    assert client.post("/stat-test", json=body).status_code == 400


# --- /attack ----------------------------------------------------------------------

def test_attack_cracks_classical_bits(client):
    run = client.get("/classical-draw?n=128").get_json()
    result = client.post("/attack", json={"bits": run["bits"]}).get_json()
    assert result["seed"] == run["seed"]
    assert result["seeds_tried"] == classical_source.SEED_SPACE
    assert result["correct"] == result["hidden_bits"] == 64
    assert result["predicted"] == run["bits"][64:]


def test_attack_cannot_crack_quantum_bits(client, mock_mode):
    bits = client.get("/quantum-draw?n=128").get_json()["bits"]
    result = client.post("/attack", json={"bits": bits}).get_json()
    assert result["seed"] is None and result["seeds_matched"] == 0
    assert 0.2 < result["accuracy"] < 0.8  # a coin flip; fails with negligible probability


def test_attack_needs_enough_bits(client):
    assert client.post("/attack", json={"bits": [0, 1] * 8}).status_code == 400


def test_find_seeds_matches_classical_draw():
    bits = classical_source.draw(40, seed=4821)["bits"]
    assert attack.find_seeds(bits) == [4821]
