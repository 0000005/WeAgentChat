from fastapi.testclient import TestClient
from types import SimpleNamespace

from app.core.config import settings
from app.api.endpoints.llm import _llm_test_tool_choice
from app.services import provider_rules


def test_deepseek_llm_test_uses_automatic_tool_choice():
    assert _llm_test_tool_choice(
        "https://api.deepseek.com/v1", "deepseek-v4-flash"
    ) == "auto"


def test_other_llm_test_forces_weather_tool():
    assert _llm_test_tool_choice(
        "https://api.openai.com/v1", "gpt-4.1"
    ) == {"type": "function", "function": {"name": "get_weather"}}


def test_deepseek_disabled_thinking_omits_reasoning_effort():
    config = SimpleNamespace(provider="openai_compatible", base_url="https://api.deepseek.com/v1")

    assert provider_rules.get_reasoning_effort(config, "deepseek-v4-flash", False) is None
    assert provider_rules.get_thinking_extra_body(config, "deepseek-v4-flash", False) == {
        "thinking": {"type": "disabled"}
    }


def test_deepseek_enabled_thinking_uses_supported_effort():
    config = SimpleNamespace(provider="openai_compatible", base_url="https://api.deepseek.com/v1")

    assert provider_rules.get_reasoning_effort(config, "deepseek-v4-flash", True) == "low"
    assert provider_rules.get_thinking_extra_body(config, "deepseek-v4-flash", True) == {
        "thinking": {"type": "enabled"}
    }

def test_get_llm_config_not_found(client: TestClient):
    """
    Test getting config when none exists.
    Should return 404 based on current implementation.
    """
    response = client.get(f"{settings.API_STR}/llm/config")
    assert response.status_code == 404
    assert response.json() == {"detail": "LLM Config not found"}

def test_create_llm_config(client: TestClient):
    """
    Test creating a new LLM configuration.
    """
    new_config = {
        "base_url": "https://api.example.com/v1",
        "api_key": "sk-test-123456",
        "model_name": "gpt-4"
    }
    response = client.put(f"{settings.API_STR}/llm/config", json=new_config)
    assert response.status_code == 200
    data = response.json()
    assert data["base_url"] == new_config["base_url"]
    assert data["api_key"] == new_config["api_key"]
    assert data["model_name"] == new_config["model_name"]
    assert "id" in data

def test_get_llm_config_existing(client: TestClient):
    """
    Test getting config after creation.
    """
    response = client.get(f"{settings.API_STR}/llm/config")
    assert response.status_code == 200
    data = response.json()
    assert data["base_url"] == "https://api.example.com/v1"
    assert data["model_name"] == "gpt-4"

def test_update_llm_config(client: TestClient):
    """
    Test updating an existing LLM configuration.
    """
    update_data = {
        "model_name": "gpt-4-turbo"
    }
    # Note: validation schema allows partial updates if we use PATCH, 
    # but our PUT endpoint uses LLMConfigUpdate which has optional fields 
    # but the service logic 'update_config' handles it. 
    # Wait, PUT usually implies full replacement, but my service logic uses `exclude_unset=True`
    # so it acts like a PATCH or "Update what's provided".
    
    response = client.put(f"{settings.API_STR}/llm/config", json=update_data)
    assert response.status_code == 200
    data = response.json()
    assert data["model_name"] == "gpt-4-turbo"
    # base_url should remain unchanged if we strictly follow the 'update existing' logic in service
    # which uses `update_data.items()` from `exclude_unset=True`.
    assert data["base_url"] == "https://api.example.com/v1" 
