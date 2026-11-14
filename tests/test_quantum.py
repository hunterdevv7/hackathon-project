import importlib.util

import pytest

from backend import config, quantum_source
from backend.app import create_app


@pytest.fixture
def client():
    return create_app().test_client()


# --- /quantum-state in mock mode --------------------------------------------

@pytest.fixture
def mock_mode(monkeypatch):
    monkeypatch.setattr(config, "QUANTUM_MODE", "mock")


def test_state_default_is_one_qubit_50_50(client, mock_mode):
    data = client.get("/quantum-state").get_json()
    assert data["engine"] == "mock" and data["source"] == "quantum" and data["n"] == 1
    assert data["qubits"] == [{"qubit": 0, "p0": 0.5, "p1": 0.5}]
    assert [s["bits"] for s in data["basis_states"]] == ["0", "1"]
    for s in data["basis_states"]:
        assert s["amplitude"] == {"re": 0.707107, "im": 0.0}  # 1/sqrt(2)
        assert s["probability"] == 0.5


def test_state_three_qubits(client, mock_mode):
    data = client.get("/quantum-state?n=3").get_json()
    assert len(data["basis_states"]) == 8 and len(data["qubits"]) == 3
    assert sum(s["probability"] for s in data["basis_states"]) == pytest.approx(1.0)


@pytest.mark.parametrize("n", ["0", "abc", "9"])
def test_state_bad_n(client, n):
    assert client.get(f"/quantum-state?n={n}").status_code == 400


def test_engine_error_is_503_not_mock(client, monkeypatch):
    """With quantumrings mode but no credentials we must error, never fake it."""
    monkeypatch.setattr(config, "QUANTUM_MODE", "quantumrings")
    monkeypatch.setattr(config, "QR_TOKEN", "")
    monkeypatch.setattr(quantum_source, "_backend", None)
    resp = client.get("/quantum-draw")
    assert resp.status_code == 503
    assert "error" in resp.get_json()


# --- Live Quantum Rings (skipped unless configured) -------------------------

live = pytest.mark.skipif(
    config.QUANTUM_MODE != "quantumrings"
    or not (config.QR_TOKEN and config.QR_ACCOUNT)
    or importlib.util.find_spec("QuantumRingsLib") is None,
    reason="needs QUANTUM_MODE=quantumrings, QR_TOKEN/QR_ACCOUNT and QuantumRingsLib",
)


@live
@pytest.mark.parametrize("n", [1, 64, 200])  # 200 > 128 exercises chunking
def test_live_draw(client, n):
    data = client.get(f"/quantum-draw?n={n}").get_json()
    assert data["engine"] == "quantumrings"
    assert len(data["bits"]) == n and set(data["bits"]) <= {0, 1}


@live
def test_live_two_draws_differ(client):
    a = client.get("/quantum-draw").get_json()["bits"]
    b = client.get("/quantum-draw").get_json()["bits"]
    assert a != b  # fails with probability 2**-64


@live
def test_live_state(client):
    data = client.get("/quantum-state?n=2").get_json()
    assert data["engine"] == "quantumrings"
    for q in data["qubits"]:
        assert q["p0"] == pytest.approx(0.5, abs=1e-4)
        assert q["p1"] == pytest.approx(0.5, abs=1e-4)
