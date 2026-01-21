"""
Unit tests for PersonaGeneratorService.
Tests cover:
1. Error when LLM config is missing
2. Error when LLM call fails
3. Successful persona generation (mocked LLM response)
4. API endpoint integration test
"""
import json
import pytest
from types import SimpleNamespace
from unittest.mock import patch, AsyncMock

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.llm import LLMConfig
from app.schemas.persona_generator import PersonaGenerateRequest, PersonaGenerateResponse
from app.services.persona_generator_service import PersonaGeneratorService, persona_generator_service
from app.services.settings_service import SettingsService


pytest_plugins = ("pytest_asyncio",)

# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def db():
    """Create a fresh database for each test."""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)

def activate_llm_config(db, llm_config):
    db.add(llm_config)
    db.commit()
    db.refresh(llm_config)
    SettingsService.set_setting(
        db,
        "chat",
        "active_llm_config_id",
        llm_config.id,
        "int",
        "当前聊天模型配置ID",
    )
    return llm_config


@pytest.mark.asyncio
class TestPersonaGeneratorService:
    """Test the PersonaGeneratorService."""

    async def test_generate_persona_no_llm_config_raises_error(self, db):
        """Test that HTTPException is raised when no LLM config exists."""
        # Ensure no LLM config in database
        db.query(LLMConfig).delete()
        db.commit()
        
        request = PersonaGenerateRequest(description="测试角色")
        
        with pytest.raises(HTTPException) as exc_info:
            await PersonaGeneratorService.generate_persona(db, request)
        
        assert exc_info.value.status_code == 500
        assert "LLM configuration not found" in exc_info.value.detail

    async def test_generate_persona_llm_success(self, db):
        """测试 LLM 成功生成 Persona（模拟真实 LLM 返回 JSON 字符串）"""
        # Setup LLM config
        llm_config = LLMConfig(
            base_url="https://api.example.com",
            api_key="test-key",
            model_name="gpt-4"
        )
        activate_llm_config(db, llm_config)
        
        # Mock LLM response - 返回纯 JSON 字符串
        mock_json_response = json.dumps({
            "name": "乔布斯先生",
            "description": "追求极致、改变世界的科技布道者",
            "system_prompt": "【身份定位】\n角色身份：苹果公司创始人...",
            "initial_message": "Stay hungry, stay foolish."
        }, ensure_ascii=False)
        
        mock_result = SimpleNamespace(final_output=mock_json_response)
        
        with patch("app.services.persona_generator_service.Runner.run", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = mock_result
            
            request = PersonaGenerateRequest(
                description="一个像乔布斯一样的产品经理"
            )
            result = await PersonaGeneratorService.generate_persona(db, request)
        
        assert isinstance(result, PersonaGenerateResponse)
        assert result.name == "乔布斯先生"
        assert result.description == "追求极致、改变世界的科技布道者"
        assert "Stay hungry" in result.initial_message

    async def test_generate_persona_llm_returns_markdown(self, db):
        """测试解析 Markdown 代码块包裹的 JSON（模拟 GLM 等模型的行为）"""
        # Setup LLM config
        llm_config = LLMConfig(
            base_url="https://api.example.com",
            api_key="test-key",
            model_name="gpt-4"
        )
        activate_llm_config(db, llm_config)
        
        # Mock LLM response - Markdown 代码块包裹的 JSON
        mock_json = {
            "name": "猫娘小雪",
            "description": "一个傲娇的猫娘",
            "system_prompt": "【身份定位】\n角色身份：猫娘...",
            "initial_message": "哼，主人你来了喵~"
        }
        markdown_response = f"```json\n{json.dumps(mock_json, ensure_ascii=False)}\n```"
        
        mock_result = SimpleNamespace(final_output=markdown_response)
        
        with patch("app.services.persona_generator_service.Runner.run", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = mock_result
            
            request = PersonaGenerateRequest(description="傲娇猫娘")
            result = await PersonaGeneratorService.generate_persona(db, request)
        
        assert result.name == "猫娘小雪"
        assert "猫娘" in result.system_prompt

    async def test_generate_persona_llm_exception_raises_error(self, db):
        """Test that HTTPException is raised when LLM call fails."""
        # Setup LLM config
        llm_config = LLMConfig(
            base_url="https://api.example.com",
            api_key="test-key",
            model_name="gpt-4"
        )
        activate_llm_config(db, llm_config)
        
        with patch("app.services.persona_generator_service.Runner.run", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = Exception("LLM API error")
            
            request = PersonaGenerateRequest(
                description="测试角色",
                name="TestName"
            )
            
            with pytest.raises(HTTPException) as exc_info:
                await PersonaGeneratorService.generate_persona(db, request)
            
            assert exc_info.value.status_code == 502
            assert "LLM call failed" in exc_info.value.detail

    async def test_generate_persona_invalid_json_raises_error(self, db):
        """Test that HTTPException is raised when LLM returns invalid JSON."""
        # Setup LLM config
        llm_config = LLMConfig(
            base_url="https://api.example.com",
            api_key="test-key",
            model_name="gpt-4"
        )
        activate_llm_config(db, llm_config)
        
        mock_result = SimpleNamespace(final_output="This is not valid JSON at all")
        
        with patch("app.services.persona_generator_service.Runner.run", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = mock_result
            
            request = PersonaGenerateRequest(description="无效响应测试")
            
            with pytest.raises(HTTPException) as exc_info:
                await PersonaGeneratorService.generate_persona(db, request)
            
            assert exc_info.value.status_code == 502
            assert "Failed to parse LLM response" in exc_info.value.detail

    async def test_generate_persona_empty_response_raises_error(self, db):
        """Test that HTTPException is raised when LLM returns empty response."""
        # Setup LLM config
        llm_config = LLMConfig(
            base_url="https://api.example.com",
            api_key="test-key",
            model_name="gpt-4"
        )
        activate_llm_config(db, llm_config)
        
        mock_result = SimpleNamespace(final_output="")
        
        with patch("app.services.persona_generator_service.Runner.run", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = mock_result
            
            request = PersonaGenerateRequest(description="空响应测试")
            
            with pytest.raises(HTTPException) as exc_info:
                await PersonaGeneratorService.generate_persona(db, request)
            
            assert exc_info.value.status_code == 502
            assert "empty response" in exc_info.value.detail

    async def test_generate_persona_missing_fields_raises_error(self, db):
        """Test that HTTPException is raised when LLM JSON is missing fields."""
        llm_config = LLMConfig(
            base_url="https://api.example.com",
            api_key="test-key",
            model_name="gpt-4"
        )
        activate_llm_config(db, llm_config)

        mock_json_response = json.dumps({
            "name": "未完成角色",
            "description": "缺少 system_prompt 和 initial_message"
        }, ensure_ascii=False)

        mock_result = SimpleNamespace(final_output=mock_json_response)

        with patch("app.services.persona_generator_service.Runner.run", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = mock_result

            request = PersonaGenerateRequest(description="字段缺失测试")

            with pytest.raises(HTTPException) as exc_info:
                await PersonaGeneratorService.generate_persona(db, request)

            assert exc_info.value.status_code == 502
            assert "missing required fields" in exc_info.value.detail


@pytest.mark.asyncio
class TestPersonaGeneratorAPI:
    """Test the API endpoint integration."""

    async def test_api_endpoint_exists(self):
        """Verify the API endpoint is registered."""
        from fastapi.testclient import TestClient
        from app.main import app

        # Check that the route exists in the app
        routes = [route.path for route in app.routes]
        # The actual path includes the API prefix
        assert any("/friend-templates/generate" in route for route in routes)
        assert any("/friend-templates/generate/stream" in route for route in routes)

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
