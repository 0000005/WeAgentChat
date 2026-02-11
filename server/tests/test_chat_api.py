from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker
from app.main import app
from app.api.deps import get_db
from app.services.settings_service import SettingsService
from tests.conftest import engine
from unittest.mock import patch, AsyncMock, MagicMock
from openai.types.responses import ResponseTextDeltaEvent
import json

MockSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def activate_llm_config(db: Session, llm_config):
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
    SettingsService.set_setting(
        db,
        "memory",
        "recall_enabled",
        False,
        "bool",
        "是否启用记忆召回功能",
    )
    return llm_config

def create_mock_event(delta, index):
    mock_event = MagicMock()
    mock_event.type = "raw_response_event"
    mock_event.data = ResponseTextDeltaEvent(
        delta=delta, 
        index=index,
        type="response.output_text.delta",
        item_id="item_1",
        content_index=0,
        output_index=0,
        sequence_number=index,
        logprobs=[]
    )
    return mock_event

def test_send_message(client: TestClient, db: Session):
    # 0. Setup LLM Config (In-memory DB starts empty)
    from app.models.llm import LLMConfig
    llm_config = LLMConfig(
        base_url="https://open.bigmodel.cn/api/coding/paas/v4", 
        api_key="mock_key",
        model_name="glm-4-flash"
    )
    activate_llm_config(db, llm_config)

    # 1. Create a Friend (needed for session)
    friend_data = {"name": "Test Friend", "is_preset": False, "system_prompt": "You are a helpful test assistant."}
    response = client.post("/api/friends/", json=friend_data)
    assert response.status_code == 200
    friend_id = response.json()["id"]

    # 2. Create a Session
    session_data = {"friend_id": friend_id, "title": "Test Chat"}
    response = client.post("/api/chat/sessions", json=session_data)
    assert response.status_code == 200
    session_id = response.json()["id"]

    # 3. Send Message (Streaming)
    msg_data = {"content": "Hello"}
    
    async def mock_stream_events():
        yield create_mock_event("Hello", 0)
        yield create_mock_event(" World", 1)

    mock_runner_result = MagicMock()
    mock_runner_result.stream_events = mock_stream_events

    with patch("app.services.chat_service.Runner.run_streamed", return_value=mock_runner_result), \
         patch("app.services.chat_service.SessionLocal", MockSessionLocal):
        response = client.post(f"/api/chat/sessions/{session_id}/messages", json=msg_data)
        assert response.status_code == 200
        
        content_received = ""
        events_received = []
        
        for line in response.iter_lines():
            line_str = line if isinstance(line, str) else line.decode('utf-8')
            if line_str.startswith("event:"):
                events_received.append(line_str.split(": ")[1])
            if line_str.startswith("data:"):
                try:
                    data = json.loads(line_str[6:])
                    if "delta" in data:
                        content_received += data["delta"]
                except:
                    pass
        
        assert "start" in events_received
        assert "message" in events_received
        assert "done" in events_received
        assert content_received == "Hello World"

    # 4. Verify History (Should be saved in DB)
    response = client.get(f"/api/chat/sessions/{session_id}/messages")
    assert response.status_code == 200
    msgs = response.json()
    assert len(msgs) == 2 
    assert msgs[1]["role"] == "assistant"
    assert msgs[1]["content"] == "Hello World"

def test_send_message_thinking(client: TestClient, db: Session):
    # 0. Setup LLM Config
    from app.models.llm import LLMConfig
    llm_config = LLMConfig(
        base_url="https://mock.url",
        api_key="mock_key",
        model_name="deepseek-r1",
        capability_reasoning=True
    )
    activate_llm_config(db, llm_config)

    # 1. Create Friend & Session
    friend_data = {"name": "Test Friend", "is_preset": False}
    p_resp = client.post("/api/friends/", json=friend_data)
    friend_id = p_resp.json()["id"]
    
    s_resp = client.post("/api/chat/sessions", json={"friend_id": friend_id})
    session_id = s_resp.json()["id"]

    # 2. Mock Stream with split tags
    async def mock_stream_events():
        # "<", "think", ">", "Thinking...", "</", "think", ">", "Result"
        chunks = ["<", "think", ">", "Thinking...", "</", "think", ">", "Result"]
        for i, c in enumerate(chunks):
            yield create_mock_event(c, i)

    mock_runner_result = MagicMock()
    mock_runner_result.stream_events = mock_stream_events

    with patch("app.services.chat_service.Runner.run_streamed", return_value=mock_runner_result), \
         patch("app.services.chat_service.SessionLocal", MockSessionLocal):
        response = client.post(f"/api/chat/sessions/{session_id}/messages", json={"content": "Hi", "enable_thinking": True})
        assert response.status_code == 200
        
        events = []
        thinking_content = ""
        message_content = ""
        
        # Helper to track last event type
        last_event = None

        for line in response.iter_lines():
            line_str = line if isinstance(line, str) else line.decode('utf-8')
            if line_str.startswith("event: "):
                last_event = line_str.split(": ")[1]
                events.append(last_event)
            if line_str.startswith("data: "):
                data = json.loads(line_str[6:])
                if last_event == "model_thinking":
                    thinking_content += data.get("delta", "")
                elif last_event == "message":
                    message_content += data.get("delta", "")

        assert "model_thinking" in events
        assert "message" in events
        assert thinking_content == "Thinking..."
        assert message_content == "Result"
        
        # Verify DB content (should NOT contain thinking tags)
        hist_resp = client.get(f"/api/chat/sessions/{session_id}/messages")
        msgs = hist_resp.json()
        assert msgs[-1]["content"] == "Result"


def test_send_message_llm_error(client: TestClient, db: Session):
    """Test that LLM errors are handled gracefully and return error event."""
    # 0. Setup LLM Config
    from app.models.llm import LLMConfig
    llm_config = LLMConfig(
        base_url="https://mock.url",
        api_key="mock_key",
        model_name="mock-model"
    )
    activate_llm_config(db, llm_config)

    # 1. Create Friend & Session
    friend_data = {"name": "Test Friend", "is_preset": False}
    p_resp = client.post("/api/friends/", json=friend_data)
    friend_id = p_resp.json()["id"]
    
    s_resp = client.post("/api/chat/sessions", json={"friend_id": friend_id})
    session_id = s_resp.json()["id"]

    # 2. Mock Runner to raise an exception
    with patch("app.services.chat_service.Runner.run_streamed", side_effect=Exception("LLM API Error")), \
         patch("app.services.chat_service.SessionLocal", MockSessionLocal):
        response = client.post(f"/api/chat/sessions/{session_id}/messages", json={"content": "Hi"})
        assert response.status_code == 200
        
        events = []
        error_detail = ""
        
        for line in response.iter_lines():
            line_str = line if isinstance(line, str) else line.decode('utf-8')
            if line_str.startswith("event: "):
                events.append(line_str.split(": ")[1])
            if line_str.startswith("data: "):
                data = json.loads(line_str[6:])
                if "detail" in data:
                    error_detail = data["detail"]

        # Should have start and error events
        assert "start" in events
        assert "error" in events
        assert "LLM API Error" in error_detail


def test_send_message_with_voice_payload(client: TestClient, db: Session):
    from app.models.llm import LLMConfig

    llm_config = LLMConfig(
        base_url="https://mock.url",
        api_key="mock_key",
        model_name="mock-model",
    )
    activate_llm_config(db, llm_config)

    friend_data = {
        "name": "Voice Friend",
        "is_preset": False,
        "enable_voice": True,
        "voice_id": "Cherry",
    }
    p_resp = client.post("/api/friends/", json=friend_data)
    assert p_resp.status_code == 200
    friend_id = p_resp.json()["id"]

    s_resp = client.post("/api/chat/sessions", json={"friend_id": friend_id})
    assert s_resp.status_code == 200
    session_id = s_resp.json()["id"]

    async def mock_stream_events():
        chunks = ["<message>你好</message>", "<message>再见</message>"]
        for i, c in enumerate(chunks):
            yield create_mock_event(c, i)

    async def fake_voice_payload(**kwargs):
        on_segment_ready = kwargs.get("on_segment_ready")
        seg0 = {"segment_index": 0, "text": "你好", "audio_url": "/uploads/audio/a0.mp3", "duration_sec": 1}
        seg1 = {"segment_index": 1, "text": "再见", "audio_url": "/uploads/audio/a1.mp3", "duration_sec": 1}
        if on_segment_ready:
            await on_segment_ready(seg0)
            await on_segment_ready(seg1)
        return {
            "voice_id": "Cherry",
            "segments": [seg0, seg1],
            "generated_at": "2026-02-11T00:00:00+00:00",
        }

    mock_runner_result = MagicMock()
    mock_runner_result.stream_events = mock_stream_events

    with patch("app.services.chat_service.Runner.run_streamed", return_value=mock_runner_result), \
         patch("app.services.chat_service.SessionLocal", MockSessionLocal), \
         patch("app.services.chat_service.generate_voice_payload_for_message", side_effect=fake_voice_payload):
        response = client.post(f"/api/chat/sessions/{session_id}/messages", json={"content": "Hi"})
        assert response.status_code == 200

        events = []
        last_event = None
        voice_segments = []
        final_voice_payload = None

        for line in response.iter_lines():
            line_str = line if isinstance(line, str) else line.decode("utf-8")
            if line_str.startswith("event: "):
                last_event = line_str.split(": ", 1)[1]
                events.append(last_event)
            if line_str.startswith("data: "):
                data = json.loads(line_str[6:])
                if last_event == "voice_segment":
                    voice_segments.append(data.get("segment"))
                elif last_event == "voice_payload":
                    final_voice_payload = data.get("voice_payload")

        assert "done" in events
        assert "voice_segment" in events
        assert "voice_payload" in events
        assert len([s for s in voice_segments if s]) == 2
        assert final_voice_payload is not None
        assert final_voice_payload["voice_id"] == "Cherry"
        assert len(final_voice_payload["segments"]) == 2

    hist_resp = client.get(f"/api/chat/sessions/{session_id}/messages")
    assert hist_resp.status_code == 200
    msgs = hist_resp.json()
    assert len(msgs) == 2
    assert msgs[-1]["voice_payload"] is not None
    assert msgs[-1]["voice_payload"]["voice_id"] == "Cherry"
    assert len(msgs[-1]["voice_payload"]["segments"]) == 2
