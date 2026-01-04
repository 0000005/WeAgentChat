import pytest
import numpy as np
import uuid
import struct
from sqlalchemy import select, func, text
from memobase_server.models.database import User, UserEvent, UserEventGist, CONFIG
from memobase_server.connectors import Session, DB_ENGINE
from memobase_server.controllers.event import search_user_events, append_user_event, filter_user_events
from memobase_server.models.database import DEFAULT_PROJECT_ID
from unittest.mock import patch, AsyncMock, Mock

def serialize_embedding(embedding: list[float]) -> bytes:
    return struct.pack(f"{len(embedding)}f", *embedding)

@pytest.fixture
def mock_embedding():
    with patch("memobase_server.controllers.event.get_embedding") as mock:
        async_mock = AsyncMock()
        async_mock.ok = Mock(return_value=True)
        # Return a deterministic embedding
        async_mock.data = Mock(return_value=np.array([[0.1] * CONFIG.embedding_dim]))
        mock.return_value = async_mock
        yield mock

@pytest.mark.asyncio
async def test_sqlite_vec_loading(db_env):
    """Test if sqlite-vec extension is loaded and functional."""
    with Session() as session:
        # Check if vec_version function exists
        try:
            result = session.execute(text("SELECT vec_version()")).scalar()
            assert result is not None
            print(f"sqlite-vec version: {result}")
        except Exception as e:
            pytest.fail(f"sqlite-vec extension not loaded: {e}")

@pytest.mark.asyncio
async def test_vector_storage_and_retrieval(db_env):
    """Test storing and retrieving vectors using the custom Vector type."""
    test_vec = [0.1, 0.2, 0.3] + [0.0] * (CONFIG.embedding_dim - 3)
    
    with Session() as session:
        # Create a user first
        user = User(project_id=DEFAULT_PROJECT_ID)
        session.add(user)
        session.commit()
        user_id = user.id

        event = UserEvent(
            user_id=user_id,
            project_id=DEFAULT_PROJECT_ID,
            event_data={"msg": "test vector"},
            embedding=test_vec
        )
        session.add(event)
        session.commit()
        event_id = event.id

    with Session() as session:
        retrieved_event = session.query(UserEvent).filter_by(id=event_id).first()
        assert retrieved_event is not None
        assert retrieved_event.embedding is not None
        assert len(retrieved_event.embedding) == CONFIG.embedding_dim
        assert np.allclose(retrieved_event.embedding[:3], [0.1, 0.2, 0.3])

@pytest.mark.asyncio
async def test_vector_similarity_search(db_env, mock_embedding):
    """Test vector similarity search using the controller."""
    user_id = str(uuid.uuid4())
    # Create user in DB
    u_uuid = uuid.UUID(user_id)
    with Session() as session:
        user = User(project_id=DEFAULT_PROJECT_ID)
        user.id = u_uuid
        session.add(user)
        session.commit()

    # Append an event with mock embedding [0.1, 0.1, ...]
    await append_user_event(u_uuid, DEFAULT_PROJECT_ID, {
        "event_tip": "test event",
        "event_tags": [{"tag": "test", "value": "val"}]
    })

    # Search with identical query (mocked to [0.1, 0.1, ...])
    result = await search_user_events(u_uuid, DEFAULT_PROJECT_ID, "query", topk=5)
    
    assert result.ok()
    events = result.data().events
    assert len(events) > 0
    # Similarity should be close to 1
    assert events[0].similarity > 0.99

@pytest.mark.asyncio
async def test_json_tag_filtering(db_env):
    """Test JSON filtering logic specifically for SQLite json_each."""
    user_id = str(uuid.uuid4())
    u_uuid = uuid.UUID(user_id)
    with Session() as session:
        user = User(project_id=DEFAULT_PROJECT_ID)
        user.id = u_uuid
        session.add(user)
        
        # Event 1: has tag 'emotion'='happy'
        session.add(UserEvent(
            user_id=u_uuid,
            project_id=DEFAULT_PROJECT_ID,
            event_data={"event_tags": [{"tag": "emotion", "value": "happy"}]},
            embedding=None
        ))
        
        # Event 2: has tag 'emotion'='sad'
        session.add(UserEvent(
            user_id=u_uuid,
            project_id=DEFAULT_PROJECT_ID,
            event_data={"event_tags": [{"tag": "emotion", "value": "sad"}]},
            embedding=None
        ))
        
        # Event 3: has tag 'action'='run'
        session.add(UserEvent(
            user_id=u_uuid,
            project_id=DEFAULT_PROJECT_ID,
            event_data={"event_tags": [{"tag": "action", "value": "run"}]},
            embedding=None
        ))
        
        session.commit()

    # Test filtering by tag name
    res1 = await filter_user_events(u_uuid, DEFAULT_PROJECT_ID, has_event_tag=["emotion"])
    assert len(res1.data().events) == 2
    
    # Test filtering by tag name and value
    res2 = await filter_user_events(u_uuid, DEFAULT_PROJECT_ID, event_tag_equal={"emotion": "happy"})
    assert len(res2.data().events) == 1
    assert res2.data().events[0].event_data.event_tags[0].tag == "emotion"
    assert res2.data().events[0].event_data.event_tags[0].value == "happy"

    # Test filtering by multiple tags (AND logic)
    res3 = await filter_user_events(u_uuid, DEFAULT_PROJECT_ID, event_tag_equal={"emotion": "happy", "action": "run"})
    assert len(res3.data().events) == 0
