async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200 and resp.json() == {"status": "ok"}
    assert "x-request-id" in resp.headers


async def test_ready_ok_and_degraded(client, queue):
    resp = await client.get("/health/ready")
    assert resp.status_code == 200 and resp.json()["database"] == "ok"
    queue.fail = True
    resp = await client.get("/health/ready")
    assert resp.status_code == 503 and resp.json()["status"] == "degraded"


async def test_admin_requires_token(client):
    assert (await client.get("/admin/stats")).status_code == 401
    bad = await client.get("/admin/stats", headers={"Authorization": "Bearer nope"})
    assert bad.status_code == 401
    ok = await client.get("/admin/stats", headers={"Authorization": "Bearer admin-secret"})
    assert ok.status_code == 200 and ok.json()["jobs_by_status"]["pending"] == 0


async def test_admin_disabled_when_no_token_configured(client, settings):
    settings.admin_token = ""
    assert (await client.get("/admin/stats")).status_code == 404
