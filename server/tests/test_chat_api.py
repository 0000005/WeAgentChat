from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.api.deps import get_db

def test_send_message(client: TestClient, db: Session):
    # 0. Setup LLM Config (In-memory DB starts empty)
    from app.models.llm import LLMConfig
    llm_config = LLMConfig(
        base_url="https://open.bigmodel.cn/api/coding/paas/v4",
        api_key="4dce12de026450fe6d485bdff7847cde.pVqEddmkBZjdBSs6",
        model_name="glm-4.7"
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

    # 3. Send Message
    msg_data = {"content": "Hello AI, who are you?"}
    response = client.post(f"/api/chat/sessions/{session_id}/messages", json=msg_data)
    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "assistant"
    assert len(data["content"]) > 0
    print(f"LLM Response in test: {data['content']}")

    # 4. Verify History
    response = client.get(f"/api/chat/sessions/{session_id}/messages")
    assert response.status_code == 200
    msgs = response.json()
    assert len(msgs) == 2 # User + Assistant
    assert msgs[0]["role"] == "user"
    assert msgs[0]["content"] == "Hello AI, who are you?"
    assert msgs[1]["role"] == "assistant"
