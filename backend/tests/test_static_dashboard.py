from fastapi import FastAPI
from fastapi.testclient import TestClient
import app.static_dashboard as dashboard


def test_unknown_api_is_json_404_while_client_navigation_keeps_spa(tmp_path, monkeypatch):
    (tmp_path / 'index.html').write_text('<html>Dashboard</html>')
    monkeypatch.setattr(dashboard, 'FRONTEND_DIST', tmp_path)
    app = FastAPI()
    @app.get('/api/real')
    def real():
        return {'ok': True}
    dashboard.mount_dashboard(app)
    with TestClient(app) as client:
        assert client.get('/api/real').json() == {'ok': True}
        response = client.get('/api/missing-health-route')
        assert response.status_code == 404
        assert response.headers['content-type'].startswith('application/json')
        assert client.get('/api').status_code == 404
        assert client.get('/portfolio').status_code == 200
        assert 'Dashboard' in client.get('/portfolio').text
