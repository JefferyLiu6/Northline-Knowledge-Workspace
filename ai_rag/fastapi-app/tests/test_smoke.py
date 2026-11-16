"""Engineering skeletal smoke test.

Only three things are verified: applications can be built up, databases connected and the uniform return format is not destroyed.
The business functionality tests are placed in the respective sections and this document does not expand with business growth.

Operating premises: MySQL started and implemented ai_rag.sql.
Run method (under fastpi-app directory): pytest
"""

from fastapi.testclient import TestClient

from main import app


def test_root_returns_success():
    """The root path returns the successful results of the uniform format, indicating that both applications and databases are in place."""
    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == "200"
    assert body["msg"] == "Request successful"


def test_login_with_wrong_password_returns_business_error():
    """Business failures are treated in a uniform manner: HTTP is still 200, code 500, msg is human."""
    with TestClient(app) as client:
        response = client.post("/login", json={"username": "admin", "password": "wrong"})
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == "500"
    assert body["msg"] == "Invalid account or password"


def test_login_success_returns_token():
    """The administrator account in the initialized data can be login and token obtained."""
    with TestClient(app) as client:
        response = client.post("/login", json={"username": "admin", "password": "admin"})
    body = response.json()
    assert body["code"] == "200"
    assert body["data"]["role"] == "ADMIN"
    assert body["data"]["token"]


def test_protected_api_without_token_returns_401_code():
    """No login to access the protected interface returns 401 business code instead of going straight for an anomaly."""
    with TestClient(app) as client:
        response = client.get("/user/selectPage")
    body = response.json()
    assert body["code"] == "401"
