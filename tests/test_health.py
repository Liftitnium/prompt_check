def test_health_creates_db(client, settings):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
    assert settings.db_path.exists()
