import pytest

from backend.app import create_app


@pytest.fixture
def client():
    return create_app().test_client()


def _assert_bits(bits, n=64):
    assert isinstance(bits, list) and len(bits) == n
    assert set(bits) <= {0, 1}


def test_quantum_draw_shape(client):
    data = client.get("/quantum-draw").get_json()
    _assert_bits(data["bits"])
    assert data["source"] == "quantum"
    assert data["engine"] == "mock"


def test_classical_draw_shape(client):
    data = client.get("/classical-draw").get_json()
    _assert_bits(data["bits"])
    assert data["source"] == "classical"
    assert isinstance(data["seed"], int)


def test_replay_reproduces_exact_bits(client):
    """The core demo claim: same seed -> identical output."""
    original = client.get("/classical-draw").get_json()
    replay = client.post("/classical-draw/replay", json={"seed": original["seed"]}).get_json()
    assert replay["bits"] == original["bits"]
    assert replay["seed"] == original["seed"]


def test_two_quantum_draws_differ(client):
    a = client.get("/quantum-draw").get_json()["bits"]
    b = client.get("/quantum-draw").get_json()["bits"]
    assert a != b  # fails with probability 2**-64


def test_custom_batch_size(client):
    _assert_bits(client.get("/quantum-draw?n=8").get_json()["bits"], n=8)
    original = client.get("/classical-draw?n=8").get_json()
    replay = client.post("/classical-draw/replay", json={"seed": original["seed"], "n": 8}).get_json()
    assert replay["bits"] == original["bits"]


@pytest.mark.parametrize("n", ["0", "abc", "5000"])
def test_bad_batch_size(client, n):
    assert client.get(f"/quantum-draw?n={n}").status_code == 400


@pytest.mark.parametrize("body", [{}, {"seed": "1234"}, {"seed": True}])
def test_replay_rejects_bad_seed(client, body):
    assert client.post("/classical-draw/replay", json=body).status_code == 400


@pytest.mark.parametrize("source", ["quantum", "classical"])
def test_stat_test_shape(client, source):
    data = client.get(f"/stat-test?source={source}").get_json()
    assert isinstance(data["pass"], bool)
    assert isinstance(data["score"], float)


def test_stat_test_bad_source(client):
    assert client.get("/stat-test?source=dice").status_code == 400
