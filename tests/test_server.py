import pytest
import httpx
from agy_cursor_bridge.server import app

@pytest.mark.asyncio
async def test_health_endpoint():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"
        assert "antigravity" in data

@pytest.mark.asyncio
async def test_models_endpoints():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Standard OpenAI models endpoint
        res = await client.get("/v1/models")
        assert res.status_code == 200
        data = res.json()
        assert data["object"] == "list"
        assert len(data["data"]) > 0

        # Cursor specific endpoint
        res_cursor = await client.get("/cursor/models")
        assert res_cursor.status_code == 200
