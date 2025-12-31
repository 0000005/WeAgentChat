from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.api.deps import get_db
from unittest.mock import patch, AsyncMock, MagicMock
from openai.types.responses import ResponseTextDeltaEvent
import json

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
    
    db.add(llm_config)
    db.commit()

    # 1. Create a Persona (needed for session)
    persona_data = {"name": "Test Persona", "is_preset": False, "system_prompt": "You are a helpful test assistant."}
    response = client.post("/api/personas/", json=persona_data)
    assert response.status_code == 200
    persona_id = response.json()["id"]

    # 2. Create a Session
    session_data = {"persona_id": persona_id, "title": "Test Chat"}
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

    with patch("app.services.chat_service.Runner.run_streamed", return_value=mock_runner_result):
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
        model_name="deepseek-r1"
    )
    db.add(llm_config)
    db.commit()

    # 1. Create Persona & Session
    persona_data = {"name": "Test Persona", "is_preset": False}
    p_resp = client.post("/api/personas/", json=persona_data)
    persona_id = p_resp.json()["id"]
    
    s_resp = client.post("/api/chat/sessions", json={"persona_id": persona_id})
    session_id = s_resp.json()["id"]

    # 2. Mock Stream with split tags
    async def mock_stream_events():
        # "<", "think", ">", "Thinking...", "</", "think", ">", "Result"
        chunks = ["<", "think", ">", "Thinking...", "</", "think", ">", "Result"]
        for i, c in enumerate(chunks):
            yield create_mock_event(c, i)

    mock_runner_result = MagicMock()
    mock_runner_result.stream_events = mock_stream_events

    with patch("app.services.chat_service.Runner.run_streamed", return_value=mock_runner_result):
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
                if last_event == "thinking":
                    thinking_content += data.get("delta", "")
                elif last_event == "message":
                    message_content += data.get("delta", "")

        assert "thinking" in events
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
    db.add(llm_config)
    db.commit()

    # 1. Create Persona & Session
    persona_data = {"name": "Test Persona", "is_preset": False}
    p_resp = client.post("/api/personas/", json=persona_data)
    persona_id = p_resp.json()["id"]
    
    s_resp = client.post("/api/chat/sessions", json={"persona_id": persona_id})
    session_id = s_resp.json()["id"]

    # 2. Mock Runner to raise an exception
    with patch("app.services.chat_service.Runner.run_streamed", side_effect=Exception("LLM API Error")):
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

        # Should have start, error, and done events
        assert "start" in events
        assert "error" in events
        assert "done" in events
        assert "LLM API Error" in error_detail