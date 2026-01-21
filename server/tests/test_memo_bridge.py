"""
Unit tests for MemoService bridge layer.

These tests verify the SDK bridge functionality without requiring
actual LLM/Embedding API calls.
"""
import uuid
import pytest
from unittest.mock import patch, AsyncMock

# Configure pytest-asyncio
pytest_plugins = ('pytest_asyncio',)


class TestMemoServiceUnwrap:
    """Tests for the _unwrap Promise handling."""

    def test_unwrap_success(self):
        """Test that successful Promise is correctly unwrapped."""
        from app.services.memo.bridge import MemoService
        from app.vendor.memobase_server.models.utils import Promise
        
        # Create a successful Promise using resolve()
        test_data = {"user_id": "123", "name": "test"}
        promise = Promise.resolve(test_data)
        
        result = MemoService._unwrap(promise)
        assert result == test_data

    def test_unwrap_failure(self):
        """Test that failed Promise raises MemoServiceException."""
        from app.services.memo.bridge import MemoService, MemoServiceException
        from app.vendor.memobase_server.models.utils import Promise
        from app.vendor.memobase_server.models.response import CODE
        
        # Create a failed Promise using reject()
        promise = Promise.reject(CODE.NOT_FOUND, "User not found")
        
        with pytest.raises(MemoServiceException):
            MemoService._unwrap(promise)


class TestMemoServiceUserManagement:
    """Tests for user management functions."""

    @pytest.mark.asyncio
    async def test_ensure_user_creates_when_not_exists(self):
        """Test ensure_user creates a new user when it doesn't exist."""
        from app.services.memo.bridge import MemoService
        from app.vendor.memobase_server.models.utils import Promise
        from app.vendor.memobase_server.models.response import CODE
        
        test_user_id = str(uuid.uuid4())
        test_space_id = "space-1"
        
        with patch('app.services.memo.bridge.get_user', new_callable=AsyncMock) as mock_get, \
             patch('app.services.memo.bridge.create_user', new_callable=AsyncMock) as mock_create:
            
            # Simulate user not found
            mock_get.return_value = Promise.reject(CODE.NOT_FOUND, "Not found")
            mock_create.return_value = Promise.resolve({"id": test_user_id})
            
            await MemoService.ensure_user(user_id=test_user_id, space_id=test_space_id)
            
            mock_get.assert_called_once()
            mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_ensure_user_skips_when_exists(self):
        """Test ensure_user does nothing when user already exists."""
        from app.services.memo.bridge import MemoService
        from app.vendor.memobase_server.models.utils import Promise
        
        with patch('app.services.memo.bridge.get_user', new_callable=AsyncMock) as mock_get, \
             patch('app.services.memo.bridge.create_user', new_callable=AsyncMock) as mock_create:
            
            # Simulate user exists
            mock_get.return_value = Promise.resolve({"id": str(uuid.uuid4())})
            
            await MemoService.ensure_user(user_id="user-123", space_id="space-1")
            
            mock_get.assert_called_once()
            mock_create.assert_not_called()


class TestMemoServiceContext:
    """Tests for context retrieval functions."""

    @pytest.mark.asyncio
    async def test_get_user_context_calls_sdk(self):
        """Test get_user_context properly calls the SDK controller."""
        from app.services.memo.bridge import MemoService
        from app.vendor.memobase_server.models.utils import Promise
        from app.vendor.memobase_server.models.response import ContextData
        
        mock_context_data = ContextData(
            context="User is a software developer who loves Python.",
            profiles=[],
            event_summaries=[]
        )
        
        with patch('app.services.memo.bridge.get_user_context', new_callable=AsyncMock) as mock_ctx:
            mock_ctx.return_value = Promise.resolve(mock_context_data)
            
            result = await MemoService.get_user_context(
                user_id="user-123",
                space_id="space-1",
                messages=[]
            )
            
            assert result.context == mock_context_data.context
            mock_ctx.assert_called_once()


class TestMemoServiceIngestion:
    """Tests for data ingestion functions."""

    @pytest.mark.asyncio
    async def test_insert_chat_creates_blob(self):
        """Test insert_chat properly creates a ChatBlob and inserts it."""
        from app.services.memo.bridge import MemoService
        from app.vendor.memobase_server.models.utils import Promise
        from app.vendor.memobase_server.models.response import IdData
        from app.vendor.memobase_server.models.blob import OpenAICompatibleMessage
        
        # Use a valid UUID for IdData
        test_uuid = uuid.uuid4()
        
        with patch('app.services.memo.bridge.insert_blob', new_callable=AsyncMock) as mock_insert, \
             patch('app.services.memo.bridge.insert_blob_to_buffer', new_callable=AsyncMock) as mock_buffer:
            mock_insert.return_value = Promise.resolve(IdData(id=test_uuid))
            mock_buffer.return_value = Promise.resolve(None)

            messages = [
                OpenAICompatibleMessage(role="user", content="Hello!"),
                OpenAICompatibleMessage(role="assistant", content="Hi there!")
            ]

            result = await MemoService.insert_chat(
                user_id=str(uuid.uuid4()),
                space_id="space-1",
                messages=messages
            )
            
            assert result.id == test_uuid
            mock_insert.assert_called_once()
            mock_buffer.assert_called_once()



class TestMemoServiceProjectConfig:
    """Tests for project configuration functions."""

    @pytest.mark.asyncio
    async def test_get_profile_config_calls_sdk(self):
        """Test get_profile_config properly calls the SDK controller."""
        from app.services.memo.bridge import MemoService
        from app.vendor.memobase_server.models.utils import Promise
        from app.vendor.memobase_server.models.response import ProfileConfigData
        
        mock_config = ProfileConfigData(profile_config="topic: Test")
        
        with patch('app.services.memo.bridge.get_project_profile_config_string', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = Promise.resolve(mock_config)
            
            result = await MemoService.get_profile_config(space_id="space-1")
            
            assert result.profile_config == "topic: Test"
            mock_get.assert_called_once_with(project_id="space-1")

    @pytest.mark.asyncio
    async def test_update_profile_config_calls_sdk(self):
        """Test update_profile_config properly calls the SDK controller."""
        from app.services.memo.bridge import MemoService
        from app.vendor.memobase_server.models.utils import Promise
        
        with patch('app.services.memo.bridge.update_project_profile_config', new_callable=AsyncMock) as mock_update:
            mock_update.return_value = Promise.resolve(None)
            
            await MemoService.update_profile_config(space_id="space-1", profile_config="new config")
            
            mock_update.assert_called_once_with(project_id="space-1", profile_config="new config")


class TestMemoServiceRecallExtensions:
    """Tests for memory recall extension functions."""

    @pytest.mark.asyncio
    async def test_recall_memory_returns_events_only(self):
        """Test recall_memory returns event summaries from gists."""
        from app.services.memo.bridge import MemoService
        from app.vendor.memobase_server.models.response import UserEventGistsData, UserEventGistData, EventGistData
        from datetime import datetime
        
        mock_events = UserEventGistsData(gists=[
            UserEventGistData(
                id=uuid.uuid4(),
                gist_data=EventGistData(content="User is a developer"),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                similarity=0.9
            ),
            UserEventGistData(
                id=uuid.uuid4(),
                gist_data=EventGistData(content="User likes Python"),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                similarity=0.8
            )
        ], events=[])
        
        with patch.object(MemoService, 'search_memories_with_tags', new_callable=AsyncMock) as mock_event_search:
            mock_event_search.return_value = mock_events
            
            result = await MemoService.recall_memory(
                user_id="user-123",
                space_id="space-1",
                query="What does the user do?",
                friend_id=1,
                timeout=5.0
            )
            
            assert "events" in result
            assert len(result["events"]) == 2
            contents = [event["content"] for event in result["events"]]
            assert "User is a developer" in contents
            assert "User likes Python" in contents

    @pytest.mark.asyncio
    async def test_recall_memory_handles_timeout(self):
        """Test recall_memory returns empty results on timeout."""
        from app.services.memo.bridge import MemoService
        import asyncio
        
        async def slow_search(*args, **kwargs):
            await asyncio.sleep(10)  # Simulate slow search
            return None
        
        with patch.object(MemoService, 'search_memories_with_tags', side_effect=slow_search):
            
            result = await MemoService.recall_memory(
                user_id="user-123",
                space_id="space-1",
                query="test",
                friend_id=1,
                timeout=0.1  # Very short timeout
            )
            
            assert result == {"events": []}

    @pytest.mark.asyncio
    async def test_recall_memory_handles_failure(self):
        """Test recall_memory raises when event search fails."""
        from app.services.memo.bridge import MemoService, MemoServiceException

        with patch.object(MemoService, 'search_memories_with_tags', side_effect=Exception("Event search failed")):
            with pytest.raises(MemoServiceException):
                await MemoService.recall_memory(
                    user_id="user-123",
                    space_id="space-1",
                    query="test",
                    friend_id=1
                )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

