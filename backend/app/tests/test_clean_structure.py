import importlib

from fastapi.testclient import TestClient


def test_health_and_workflow_routes(foundation_db):
    import app.main as main

    importlib.reload(main)
    with TestClient(main.app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    paths = set(main.app.openapi()["paths"])
    assert "/api/v1/auth/login" in paths
    assert "/api/v1/projects" in paths
    assert "/api/v1/projects/{project_id}/workflow/summary" in paths
    assert "/api/v1/projects/{project_id}/workflow/floors/{floor_id}/calibration" in paths
    assert "/api/v1/projects/{project_id}/jobs" in paths
