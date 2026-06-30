import pytest
from fastapi.testclient import TestClient
from api_server import app, is_scanning

client = TestClient(app)

def test_health_endpoint():
    """Testuje czy Watchdogi zwracają poprawny format JSON na ścieżce /health"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "klipper" in data
    assert "camera" in data
    assert "uptime_seconds" in data

def test_scan_projects():
    """Sprawdza listowanie projektów"""
    response = client.get("/scan/projects")
    assert response.status_code == 200
    assert "projects" in response.json()

def test_motor_home_when_not_scanning():
    """Sprawdza wywołanie home(), gdy skanowanie nie jest aktywne."""
    # Symulacja, że nie ma aktywnego skanowania
    response = client.post("/motor/home")
    assert response.status_code == 200
    assert response.json()["message"] == "Zakończono bazowanie osi (G28)"

def test_start_scan_validation():
    """Weryfikuje rzucanie błędu 422 przy brakujących parametrach (pydantic validation)"""
    response = client.post("/scan/start", json={"x_min": 0})  # Brak project_name
    assert response.status_code == 422
