import pytest
import asyncio
import json
from unittest.mock import patch, MagicMock, AsyncMock
from app.models.llm import LLMConfig
from app.models.chat import Message
from tests.conftest import engine
from app.services.settings_service import SettingsService
from sqlalchemy.orm import sessionmaker

# 必须启用 pytest-asyncio
pytest_plugins = ('pytest_asyncio',)

def create_mock_event(delta, index):
    from openai.types.responses import ResponseTextDeltaEvent
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
async def test_chat_persistence_after_disconnect(client, db):
    """
    测试：即便前端中途断开 SSE 连接，后端仍能完成 LLM 回复的生成并持久化到数据库。
    """
    # 0. 设置 Mock LLM 配置
    llm_config = LLMConfig(
        base_url="https://mock.url", 
        api_key="mock_key",
        model_name="mock-model"
    )
    activate_llm_config(db, llm_config)

    # 1. 创建好友和会话
    friend_data = {"name": "Assistant", "is_preset": False}
    response = client.post("/api/friends/", json=friend_data)
    friend_id = response.json()["id"]

    response = client.post("/api/chat/sessions", json={"friend_id": friend_id})
    session_id = response.json()["id"]

    # 2. 模拟一个较长的流式回复
    async def mock_stream_events():
        chunks = ["This ", "is ", "a ", "persisted ", "response."]
        for i, chunk in enumerate(chunks):
            await asyncio.sleep(0.05) 
            yield create_mock_event(chunk, i)

    mock_runner_result = MagicMock()
    mock_runner_result.stream_events = mock_stream_events

    # Patch SessionLocal 为指向测试用的 engine 的 sessionmaker
    MockSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Mock 外部服务以防阻塞
    mock_recall_func = AsyncMock(return_value={"injected_messages": [], "footprints": []})
    mock_memo_func = AsyncMock(return_value=MagicMock(profiles=[]))

    with patch("app.services.chat_service.Runner.run_streamed", return_value=mock_runner_result), \
         patch("app.services.chat_service.SessionLocal", MockSessionLocal), \
         patch("app.services.chat_service.RecallService.perform_recall", mock_recall_func), \
         patch("app.services.chat_service.MemoService.get_user_profiles", mock_memo_func), \
         patch("app.services.chat_service.AsyncOpenAI", return_value=MagicMock()):
        
        # 3. 发送消息并故意中途断开
        msg_data = {"content": "Hello, stay alive!"}
        
        # TestClient.stream 是同步的，但在内部它会处理应用逻辑。
        # 我们模拟快速断开的过程。
        with client.stream("POST", f"/api/chat/sessions/{session_id}/messages", json=msg_data) as response:
            assert response.status_code == 200
            
            # 我们只读一个 event 就断开
            it = response.iter_lines()
            next(it) # event: start
            next(it) # data: {...}
            print("Simulated client disconnect...")

        # 4. 关键：等待异步后台任务跑完
        # 因为任务是 asyncio.create_task 发起的，它会在同一个事件循环运行。
        # 我们需要 await 一个异步挂起的操作，让出控制权给任务。
        await asyncio.sleep(0.5)
        
        # 5. 验证数据库
        db.expire_all()
        messages = db.query(Message).filter(Message.session_id == session_id, Message.role == "assistant").all()
        
        assert len(messages) == 1
        ai_msg = messages[0]
        expected_content = "This is a persisted response."
        
        print(f"Verified Database content: '{ai_msg.content}'")
        assert ai_msg.content == expected_content
