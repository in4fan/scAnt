import pytest
from fastapi.testclient import TestClient
import api_server
import health_monitor


class DummyCamera:
    def capture_image(self, output_path):
        return output_path


class DummyScanner:
    def __init__(self):
        self.images_taken = 0
        self.images_to_take = 0
        self.cancel_requested = False
        self.cam = None

    def initCam(self, cam):
        self.cam = cam

    def getProgress(self):
        return 0

    def home(self):
        return None

    def moveRelative(self, axis, distance):
        return (axis, distance)

    def deEnergise(self):
        return None

    def get_position(self):
        return {"x": 0, "y": 0, "z": 0}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(health_monitor, "start_watchdogs", lambda: None)
    monkeypatch.setattr(health_monitor, "stop_watchdogs", lambda: None)
    api_server.app.state.scanner = DummyScanner()
    api_server.app.state.camera = DummyCamera()
    api_server.app.state.scanner.initCam(api_server.app.state.camera)

    with TestClient(api_server.app) as client:
        yield client

    api_server.app.state.scanner = None
    api_server.app.state.camera = None

def test_health_endpoint(client):
    """Testuje czy Watchdogi zwracają poprawny format JSON na ścieżce /health"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "klipper" in data
    assert "camera" in data
    assert "uptime_seconds" in data

def test_scan_projects(client):
    """Sprawdza listowanie projektów"""
    response = client.get("/scan/projects")
    assert response.status_code == 200
    assert "projects" in response.json()

def test_motor_home_when_not_scanning(client):
    """Sprawdza wywołanie home(), gdy skanowanie nie jest aktywne."""
    # Symulacja, że nie ma aktywnego skanowania
    response = client.post("/motor/home")
    assert response.status_code == 200
    assert response.json()["message"] == "Zakończono bazowanie osi (G28)"

def test_start_scan_validation(client):
    """Weryfikuje rzucanie błędu 422 przy brakujących parametrach (pydantic validation)"""
    response = client.post("/scan/start", json={"x_min": 0})  # Brak project_name
    assert response.status_code == 422
