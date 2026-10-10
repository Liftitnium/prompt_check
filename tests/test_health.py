def test_health_creates_db(client, settings):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
    assert settings.db_path.exists()


def test_root_serves_the_ui(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert '<script src="/static/app.js"' in resp.text
    assert client.get("/static/app.css").status_code == 200
