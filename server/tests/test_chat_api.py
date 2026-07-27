from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker
from app.main import app
from app.api.deps import get_db
from app.services.settings_service import SettingsService
from app.models.book import Book as BookModel
from app.models.chat import ChatSession, Message
from app.services.book_reading_tools import BOOK_CONTEXT_MESSAGE_ROLE
from app.services.voice_message_service import _build_single_chat_context
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

def create_book(db: Session, title: str, friend_id: int | None):
    book = BookModel(
        title=title,
        author="测试作者",
        file_name=f"{title}.epub",
        file_path=f"/tmp/{title}.epub",
        status="ready",
        ai_friend_id=friend_id,
    )
    db.add(book)
    db.commit()
    db.refresh(book)
    return book

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
        seg0 = {"segment_index": 0, "text": "你好", "audio_url": "/uploads/audio/a0.mp3", "duration_sec": 1}
        seg1 = {"segment_index": 1, "text": "再见", "audio_url": "/uploads/audio/a1.mp3", "duration_sec": 1}
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
        done_voice_payload = None

        for line in response.iter_lines():
            line_str = line if isinstance(line, str) else line.decode("utf-8")
            if line_str.startswith("event: "):
                last_event = line_str.split(": ", 1)[1]
                events.append(last_event)
            if line_str.startswith("data: "):
                data = json.loads(line_str[6:])
                if last_event == "done":
                    done_voice_payload = data.get("voice_payload")

        assert "done" in events
        assert "voice_segment" not in events
        assert "voice_payload" not in events
        assert done_voice_payload is not None
        assert done_voice_payload["voice_id"] == "Cherry"
        assert len(done_voice_payload["segments"]) == 2

    hist_resp = client.get(f"/api/chat/sessions/{session_id}/messages")
    assert hist_resp.status_code == 200
    msgs = hist_resp.json()
    assert len(msgs) == 2
    assert msgs[-1]["voice_payload"] is not None
    assert msgs[-1]["voice_payload"]["voice_id"] == "Cherry"
    assert len(msgs[-1]["voice_payload"]["segments"]) == 2


def test_book_reading_message_isolated_by_book_and_mock_tool_context_injected(client: TestClient, db: Session):
    from app.models.llm import LLMConfig

    llm_config = LLMConfig(
        base_url="https://mock.url",
        api_key="mock_key",
        model_name="mock-model",
    )
    activate_llm_config(db, llm_config)

    friend_data = {"name": "伴读作者", "is_preset": False, "system_prompt": "你是一个乐于讲解的作者。"}
    friend_resp = client.post("/api/friends/", json=friend_data)
    assert friend_resp.status_code == 200
    friend_id = friend_resp.json()["id"]

    book_a = create_book(db, "A书", friend_id)
    book_b = create_book(db, "B书", friend_id)

    async def mock_stream_events():
        yield create_mock_event("这是", 0)
        yield create_mock_event("伴读回答", 1)

    mock_runner_result = MagicMock()
    mock_runner_result.stream_events = mock_stream_events

    with patch("app.services.chat_service.Runner.run_streamed", return_value=mock_runner_result) as mocked_runner, \
         patch("app.services.chat_service.RecallService.perform_recall", new_callable=AsyncMock) as mocked_recall, \
         patch("app.services.chat_service.SessionLocal", MockSessionLocal):
        response = client.post(
            "/api/chat/book-reading/messages",
            json={
                "user_message": "你看刚刚那句话是什么意思？",
                "book_id": book_a.id,
                "friend_id": friend_id,
                "page_context": {
                    "supported": True,
                    "reason": "ok",
                    "excerpt": "这是一段当前页正文，用来测试伴读上下文。",
                    "locator": "第 12 页",
                    "tocPath": ["第一章", "第二节"],
                    "truncated": False,
                    "sourceType": "epub",
                },
                "selected_quote": {
                    "text": "可真正的当单季净利润增长135%，累计60%的归母净利润同比增速摆在眼前。",
                    "excerpt": "可真正的当单季净利润增长135%，累计60%的归母净利润同比增速摆在眼前。",
                    "locator": "位置 395",
                    "tocPath": ["第四季度的消费股加速和科技股预演"],
                    "truncated": False,
                    "sourceType": "epub",
                },
            },
        )
        assert response.status_code == 200

        events = []
        final_content = ""
        last_event = None
        for line in response.iter_lines():
            line_str = line if isinstance(line, str) else line.decode("utf-8")
            if line_str.startswith("event: "):
                last_event = line_str.split(": ", 1)[1]
                events.append(last_event)
            if line_str.startswith("data: ") and last_event == "message":
                data = json.loads(line_str[6:])
                final_content += data.get("delta", "")

        assert "start" in events
        assert "message" in events
        assert "done" in events
        assert final_content == "这是伴读回答"

        run_messages = mocked_runner.call_args.args[1]
        assert any(msg.get("type") == "function_call" and msg.get("name") == "get_page_content" for msg in run_messages)
        assert any(msg.get("type") == "function_call" and msg.get("name") == "get_selected_content" for msg in run_messages)
        assert any(msg.get("type") == "function_call_output" and "这是一段当前页正文" in str(msg.get("output", "")) for msg in run_messages)
        assert any(msg.get("type") == "function_call_output" and "单季净利润增长135%" in str(msg.get("output", "")) for msg in run_messages)
        assert not any(msg.get("role") == "system" and "这是一段当前页正文" in msg.get("content", "") for msg in run_messages)
        assert run_messages[-1]["role"] == "user"
        assert run_messages[-1]["content"] == "你看刚刚那句话是什么意思？"
        mocked_recall.assert_not_awaited()

    book_a_messages = client.get(f"/api/chat/book-reading/messages?book_id={book_a.id}&friend_id={friend_id}")
    assert book_a_messages.status_code == 200
    book_a_payload = book_a_messages.json()
    assert len(book_a_payload) == 2
    assert book_a_payload[-1]["content"] == "这是伴读回答"

    book_b_messages = client.get(f"/api/chat/book-reading/messages?book_id={book_b.id}&friend_id={friend_id}")
    assert book_b_messages.status_code == 200
    assert book_b_messages.json() == []

    normal_friend_messages = client.get(f"/api/chat/friends/{friend_id}/messages")
    assert normal_friend_messages.status_code == 200
    assert normal_friend_messages.json() == []

    book_sessions = (
        db.query(ChatSession)
        .filter(
            ChatSession.friend_id == friend_id,
            ChatSession.session_type == "book_reading",
            ChatSession.knowledge_id == book_a.id,
        )
        .all()
    )
    assert len(book_sessions) == 1
    hidden_context_count = (
        db.query(Message)
        .filter(
            Message.session_id == book_sessions[0].id,
            Message.role == BOOK_CONTEXT_MESSAGE_ROLE,
            Message.deleted == False,
        )
        .count()
    )
    assert hidden_context_count == 4


def test_book_reading_follow_up_reuses_persisted_mock_tool_history_when_payload_omits_context(
    client: TestClient,
    db: Session,
):
    from app.models.llm import LLMConfig

    llm_config = LLMConfig(
        base_url="https://mock.url",
        api_key="mock_key",
        model_name="mock-model",
    )
    activate_llm_config(db, llm_config)

    friend_resp = client.post("/api/friends/", json={"name": "伴读作者", "is_preset": False})
    assert friend_resp.status_code == 200
    friend_id = friend_resp.json()["id"]
    book = create_book(db, "复用上下文测试", friend_id)

    async def mock_stream_events():
        yield create_mock_event("这是", 0)
        yield create_mock_event("伴读回答", 1)

    mock_runner_result = MagicMock()
    mock_runner_result.stream_events = mock_stream_events

    with patch("app.services.chat_service.Runner.run_streamed", return_value=mock_runner_result) as mocked_runner, \
         patch("app.services.chat_service.RecallService.perform_recall", new_callable=AsyncMock) as mocked_recall, \
         patch("app.services.chat_service.SessionLocal", MockSessionLocal):
        first_response = client.post(
            "/api/chat/book-reading/messages",
            json={
                "user_message": "第一页讲了什么？",
                "book_id": book.id,
                "friend_id": friend_id,
                "page_context": {
                    "supported": True,
                    "reason": "ok",
                    "excerpt": "第一页正文快照，用于验证后续追问时是否能复用。",
                    "locator": "第 8 页",
                    "tocPath": ["第一章"],
                    "truncated": False,
                    "sourceType": "epub",
                },
                "selected_quote": {
                    "text": "这是第一页选中的句子。",
                    "excerpt": "这是第一页选中的句子。",
                    "locator": "位置 88",
                    "tocPath": ["第一章"],
                    "truncated": False,
                    "sourceType": "epub",
                },
            },
        )
        assert first_response.status_code == 200
        list(first_response.iter_lines())

        second_response = client.post(
            "/api/chat/book-reading/messages",
            json={
                "user_message": "那这句话和上一段是什么关系？",
                "book_id": book.id,
                "friend_id": friend_id,
            },
        )
        assert second_response.status_code == 200
        list(second_response.iter_lines())

        assert mocked_runner.call_count == 2
        first_run_messages = mocked_runner.call_args_list[0].args[1]
        second_run_messages = mocked_runner.call_args_list[1].args[1]

        assert any(msg.get("type") == "function_call_output" and "第一页正文快照" in str(msg.get("output", "")) for msg in first_run_messages)
        assert any(msg.get("type") == "function_call_output" and "第一页正文快照" in str(msg.get("output", "")) for msg in second_run_messages)
        assert any(msg.get("type") == "function_call_output" and "第一页选中的句子" in str(msg.get("output", "")) for msg in second_run_messages)
        assert second_run_messages[-1]["role"] == "user"
        assert second_run_messages[-1]["content"] == "那这句话和上一段是什么关系？"
        mocked_recall.assert_not_awaited()

    visible_messages = client.get(f"/api/chat/book-reading/messages?book_id={book.id}&friend_id={friend_id}")
    assert visible_messages.status_code == 200
    assert len(visible_messages.json()) == 4


def test_book_reading_recall_also_deletes_hidden_context(client: TestClient, db: Session):
    from app.models.llm import LLMConfig

    llm_config = LLMConfig(
        base_url="https://mock.url",
        api_key="mock_key",
        model_name="mock-model",
    )
    activate_llm_config(db, llm_config)

    friend_resp = client.post("/api/friends/", json={"name": "伴读作者", "is_preset": False})
    assert friend_resp.status_code == 200
    friend_id = friend_resp.json()["id"]
    book = create_book(db, "撤回上下文测试", friend_id)

    async def mock_stream_events():
        yield create_mock_event("这是", 0)
        yield create_mock_event("伴读回答", 1)

    mock_runner_result = MagicMock()
    mock_runner_result.stream_events = mock_stream_events

    with patch("app.services.chat_service.Runner.run_streamed", return_value=mock_runner_result), \
         patch("app.services.chat_service.RecallService.perform_recall", new_callable=AsyncMock), \
         patch("app.services.chat_service.SessionLocal", MockSessionLocal):
        response = client.post(
            "/api/chat/book-reading/messages",
            json={
                "user_message": "这段话是什么意思？",
                "book_id": book.id,
                "friend_id": friend_id,
                "page_context": {
                    "supported": True,
                    "excerpt": "这里是撤回前的页面正文。",
                    "locator": "第 3 页",
                    "tocPath": ["第一章"],
                    "truncated": False,
                    "sourceType": "epub",
                },
                "selected_quote": {
                    "text": "这里是撤回前的引用。",
                    "excerpt": "这里是撤回前的引用。",
                    "locator": "位置 21",
                    "tocPath": ["第一章"],
                    "truncated": False,
                    "sourceType": "epub",
                },
            },
        )
        assert response.status_code == 200

        last_event = None
        session_id = None
        user_message_id = None
        for line in response.iter_lines():
            line_str = line if isinstance(line, str) else line.decode("utf-8")
            if line_str.startswith("event: "):
                last_event = line_str.split(": ", 1)[1]
            elif line_str.startswith("data: ") and last_event == "start":
                data = json.loads(line_str[6:])
                session_id = data["session_id"]
                user_message_id = data["user_message_id"]

        assert session_id is not None
        assert user_message_id is not None

        recall_resp = client.post(f"/api/chat/messages/{user_message_id}/recall")
        assert recall_resp.status_code == 200

    db.expire_all()
    remaining_hidden = (
        db.query(Message)
        .filter(
            Message.session_id == session_id,
            Message.role == BOOK_CONTEXT_MESSAGE_ROLE,
            Message.deleted == False,
        )
        .count()
    )
    assert remaining_hidden == 0

    recalled_user = db.query(Message).filter(Message.id == user_message_id).first()
    assert recalled_user is not None
    assert recalled_user.role == "system"

    recalled_assistant = (
        db.query(Message)
        .filter(Message.session_id == session_id, Message.role == "assistant")
        .order_by(Message.id.desc())
        .first()
    )
    assert recalled_assistant is not None
    assert recalled_assistant.deleted is True


def test_book_reading_disables_voice_even_if_author_has_voice_enabled(client: TestClient, db: Session):
    from app.models.llm import LLMConfig

    llm_config = LLMConfig(
        base_url="https://mock.url",
        api_key="mock_key",
        model_name="mock-model",
    )
    activate_llm_config(db, llm_config)

    friend_resp = client.post(
        "/api/friends/",
        json={
            "name": "会说话的作者",
            "is_preset": False,
            "enable_voice": True,
            "voice_id": "Cherry",
        },
    )
    assert friend_resp.status_code == 200
    friend_id = friend_resp.json()["id"]
    book = create_book(db, "伴读禁语音测试", friend_id)

    async def mock_stream_events():
        yield create_mock_event("这是", 0)
        yield create_mock_event("纯文本回答", 1)

    mock_runner_result = MagicMock()
    mock_runner_result.stream_events = mock_stream_events

    with patch("app.services.chat_service.Runner.run_streamed", return_value=mock_runner_result), \
         patch("app.services.chat_service.RecallService.perform_recall", new_callable=AsyncMock), \
         patch("app.services.chat_service.SessionLocal", MockSessionLocal), \
         patch("app.services.chat_service.generate_voice_payload_for_message", new_callable=AsyncMock) as mocked_voice:
        response = client.post(
            "/api/chat/book-reading/messages",
            json={
                "user_message": "这一页怎么理解？",
                "book_id": book.id,
                "friend_id": friend_id,
                "page_context": {
                    "supported": True,
                    "excerpt": "这是伴读页面正文。",
                    "locator": "第 16 页",
                    "tocPath": ["第二章"],
                    "truncated": False,
                    "sourceType": "epub",
                },
            },
        )
        assert response.status_code == 200

        last_event = None
        done_voice_payload = None
        for line in response.iter_lines():
            line_str = line if isinstance(line, str) else line.decode("utf-8")
            if line_str.startswith("event: "):
                last_event = line_str.split(": ", 1)[1]
            elif line_str.startswith("data: ") and last_event == "done":
                done_voice_payload = json.loads(line_str[6:]).get("voice_payload")

        mocked_voice.assert_not_awaited()
        assert done_voice_payload is None

    visible_messages = client.get(f"/api/chat/book-reading/messages?book_id={book.id}&friend_id={friend_id}")
    assert visible_messages.status_code == 200
    payload = visible_messages.json()
    assert len(payload) == 2
    assert payload[-1]["voice_payload"] is None


def test_tts_emotion_context_skips_book_context_messages(db: Session):
    from app.models.friend import Friend

    friend = Friend(name="语音测试好友", is_preset=False)
    db.add(friend)
    db.commit()
    db.refresh(friend)

    session = ChatSession(friend_id=friend.id, title="语音上下文")
    db.add(session)
    db.commit()
    db.refresh(session)

    hidden = Message(
        session_id=session.id,
        friend_id=friend.id,
        role=BOOK_CONTEXT_MESSAGE_ROLE,
        content='{"type":"function_call_output","output":"隐藏正文"}',
    )
    user = Message(session_id=session.id, role="user", content="用户问题")
    assistant = Message(session_id=session.id, role="assistant", content="助手回答")
    db.add_all([hidden, user, assistant])
    db.commit()
    db.refresh(assistant)

    context = _build_single_chat_context(db, assistant)

    assert "隐藏正文" not in context
    assert "book_context" not in context
    assert "用户: 用户问题" in context


def test_book_reading_rejects_unbound_book_without_creating_session(client: TestClient, db: Session):
    friend_resp = client.post("/api/friends/", json={"name": "未绑定作者", "is_preset": False})
    assert friend_resp.status_code == 200
    friend_id = friend_resp.json()["id"]

    unbound_book = create_book(db, "未绑定图书", None)

    response = client.post(
        "/api/chat/book-reading/messages",
        json={
            "user_message": "能聊聊这一页吗？",
            "book_id": unbound_book.id,
            "friend_id": friend_id,
            "page_context": {
                "supported": False,
                "reason": "book-unbound",
                "excerpt": "",
                "locator": "",
                "tocPath": [],
                "truncated": False,
                "sourceType": "epub",
            },
        },
    )
    assert response.status_code == 400
    assert "未绑定作者" in response.json()["detail"]

    session_count = (
        db.query(ChatSession)
        .filter(
            ChatSession.session_type == "book_reading",
            ChatSession.knowledge_id == unbound_book.id,
        )
        .count()
    )
    assert session_count == 0
