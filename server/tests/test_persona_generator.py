"""
API tests for persona generator (stream only).
"""
import pytest
from app.services.persona_generator_service import persona_generator_service


pytest_plugins = ("pytest_asyncio",)


@pytest.mark.asyncio
class TestPersonaGeneratorAPI:
    """Test the API endpoint integration."""

    async def test_stream_endpoint_exists(self):
        """Verify the stream API endpoint is registered."""
        from fastapi.testclient import TestClient
        from app.main import app

        routes = [route.path for route in app.routes]
        assert any(route.endswith("/friend-templates/generate/stream") for route in routes)
        assert not any(route.endswith("/friend-templates/generate") for route in routes)

    async def test_stream_endpoint_returns_sse_frames(self, monkeypatch):
        """Verify SSE endpoint yields delta and result frames."""
        from fastapi.testclient import TestClient
        from app.main import app

        async def fake_stream(db, payload):
            yield {"event": "delta", "data": {"delta": "正在生成..."}}
            yield {"event": "result", "data": {
                "name": "测试角色",
                "description": "测试描述",
                "system_prompt": "测试 prompt",
                "initial_message": "你好"
            }}

        monkeypatch.setattr(persona_generator_service, "generate_persona_stream", fake_stream)

        with TestClient(app) as client:
            with client.stream("POST", "/api/friend-templates/generate/stream", json={
                "description": "测试角色"
            }) as response:
                assert response.status_code == 200
                body = "".join(list(response.iter_text()))

        assert "event: delta" in body
        assert "event: result" in body
