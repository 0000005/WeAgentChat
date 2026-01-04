import asyncio
import logging
from typing import List, Optional
from app.core.config import settings
from app.vendor.memobase_server.connectors import init_db
from app.vendor.memobase_server.env import reinitialize_config
from app.vendor.memobase_server.controllers.buffer_background import start_memobase_worker

# SDK Controllers
from app.vendor.memobase_server.controllers.user import get_user, create_user, delete_user
from app.vendor.memobase_server.controllers.profile import (
    get_user_profiles, add_user_profiles, update_user_profiles, delete_user_profiles
)
from app.vendor.memobase_server.controllers.event import (
    get_user_events, append_user_event, update_user_event, delete_user_event, search_user_events
)
from app.vendor.memobase_server.controllers.context import get_user_context
from app.vendor.memobase_server.controllers.blob import insert_blob
from app.vendor.memobase_server.controllers.event_gist import search_user_event_gists, get_user_event_gists
from app.vendor.memobase_server.controllers.buffer import flush_buffer

# SDK Models
from app.vendor.memobase_server.models.response import (
    UserProfilesData, ContextData, IdData, UserData, UserEventGistsData, IdsData, UserEventsData
)
from app.vendor.memobase_server.models.blob import BlobData, BlobType, ChatBlob, OpenAICompatibleMessage
from app.vendor.memobase_server.models.utils import PromiseUnpackError
from app.vendor.memobase_server.models.response import CODE


class MemoServiceException(Exception):
    """Exception raised by MemoService for Memobase SDK errors."""
    pass


# SDK LLM/Embedding Sanity Checks
from app.vendor.memobase_server.llms import llm_sanity_check
from app.vendor.memobase_server.llms.embeddings import check_embedding_sanity


async def initialize_memo_sdk():
    """
    Initialize the Memobase SDK with settings from the main app.
    """
    # 1. Map main app settings to Memobase config
    memo_config = {
        "llm_api_key": settings.MEMOBASE_LLM_API_KEY,
        "llm_base_url": settings.MEMOBASE_LLM_BASE_URL,
        "best_llm_model": settings.MEMOBASE_BEST_LLM_MODEL,
        "enable_event_embedding": settings.MEMOBASE_ENABLE_EVENT_EMBEDDING,
        "embedding_api_key": settings.MEMOBASE_EMBEDDING_API_KEY,
        "embedding_base_url": settings.MEMOBASE_EMBEDDING_BASE_URL,
        "embedding_model": settings.MEMOBASE_EMBEDDING_MODEL,
        "embedding_dim": settings.MEMOBASE_EMBEDDING_DIM,
    }
    
    # 2. Reinitialize the global CONFIG object in SDK
    reinitialize_config(memo_config)
    
    # 3. Initialize Database
    init_db(settings.MEMOBASE_DB_URL)
    
    # 4. Perform Sanity Checks (Optional but recommended)
    logger = logging.getLogger(__name__)
    try:
        await check_embedding_sanity()
        await llm_sanity_check()
        logger.info("Memobase SDK sanity checks passed.")
    except Exception as e:
        # Log warning but don't fail - allows graceful degradation
        logger.warning(f"Memobase SDK Sanity Check Failed: {e}. Memory features may not work correctly.")
    
    # 5. Start background worker
    worker_task = asyncio.create_task(start_memobase_worker(interval_s=60))
    
    return worker_task


class MemoService:
    """
    Bridge service for Memobase SDK.
    Map project_id to space_id for consistency with the main app.
    """

    @staticmethod
    def _unwrap(promise):
        """Unwrap Promise object and raise MemoServiceException on failure."""
        try:
            return promise.data()
        except PromiseUnpackError as e:
            raise MemoServiceException(str(e)) from e

    # --- User Management ---

    @classmethod
    async def ensure_user(cls, user_id: str, space_id: str) -> None:
        """
        Ensures a user exists in the memory system.
        """
        p_get = await get_user(user_id=user_id, project_id=space_id)
        if p_get.ok():
            return
        
        if p_get.code() == CODE.NOT_FOUND:
            user_data = UserData(id=user_id)
            p_create = await create_user(data=user_data, project_id=space_id)
            cls._unwrap(p_create)
        else:
            cls._unwrap(p_get)

    @classmethod
    async def delete_user(cls, user_id: str, space_id: str) -> None:
        """
        Deletes a user and all their associated data from memory.
        """
        promise = await delete_user(user_id=user_id, project_id=space_id)
        cls._unwrap(promise)

    # --- Profile Management ---

    @classmethod
    async def get_user_profiles(cls, user_id: str, space_id: str) -> UserProfilesData:
        """
        Retrieves user profiles for a given user and space.
        """
        promise = await get_user_profiles(user_id=user_id, project_id=space_id)
        return cls._unwrap(promise)

    @classmethod
    async def add_user_profiles(
        cls, user_id: str, space_id: str, contents: List[str], attributes: List[dict]
    ) -> IdsData:
        """
        Manually adds profile entries.
        """
        promise = await add_user_profiles(
            user_id=user_id, project_id=space_id, profiles=contents, attributes=attributes
        )
        return cls._unwrap(promise)

    @classmethod
    async def update_user_profiles(
        cls, 
        user_id: str, 
        space_id: str, 
        profile_ids: List[str], 
        contents: List[str], 
        attributes: List[Optional[dict]]
    ) -> IdsData:
        """
        Manually updates profile entries.
        """
        promise = await update_user_profiles(
            user_id=user_id, 
            project_id=space_id, 
            profile_ids=profile_ids, 
            contents=contents, 
            attributes=attributes
        )
        return cls._unwrap(promise)

    @classmethod
    async def delete_user_profiles(
        cls, user_id: str, space_id: str, profile_ids: List[str]
    ) -> IdsData:
        """
        Manually deletes profile entries.
        """
        promise = await delete_user_profiles(
            user_id=user_id, project_id=space_id, profile_ids=profile_ids
        )
        return cls._unwrap(promise)

    # --- Event Management (Full Data) ---

    @classmethod
    async def get_user_events(
        cls, user_id: str, space_id: str, topk: int = 10, time_range_in_days: int = 30
    ) -> UserEventsData:
        """
        Retrieves full event records for a user.
        """
        promise = await get_user_events(
            user_id=user_id, project_id=space_id, topk=topk, time_range_in_days=time_range_in_days
        )
        return cls._unwrap(promise)

    @classmethod
    async def add_user_event(
        cls, user_id: str, space_id: str, event_data: dict
    ) -> str:
        """
        Manually appends an event. Note: this will also generate event gists and embeddings if enabled.
        """
        promise = await append_user_event(
            user_id=user_id, project_id=space_id, event_data=event_data
        )
        return cls._unwrap(promise)

    @classmethod
    async def update_user_event(
        cls, user_id: str, space_id: str, event_id: str, event_data: dict
    ) -> None:
        """
        Updates an existing event's data.
        """
        promise = await update_user_event(
            user_id=user_id, project_id=space_id, event_id=event_id, event_data=event_data
        )
        cls._unwrap(promise)

    @classmethod
    async def delete_user_event(
        cls, user_id: str, space_id: str, event_id: str
    ) -> None:
        """
        Deletes an event and its associated gists.
        """
        promise = await delete_user_event(
            user_id=user_id, project_id=space_id, event_id=event_id
        )
        cls._unwrap(promise)

    @classmethod
    async def search_full_events(
        cls, 
        user_id: str, 
        space_id: str, 
        query: str, 
        topk: int = 10, 
        similarity_threshold: float = 0.5
    ) -> UserEventsData:
        """
        Searches for full event records using vector similarity.
        """
        promise = await search_user_events(
            user_id=user_id,
            project_id=space_id,
            query=query,
            topk=topk,
            similarity_threshold=similarity_threshold,
            time_range_in_days=365,
        )
        return cls._unwrap(promise)

    # --- Context & Search ---

    @classmethod
    async def get_user_context(
        cls, 
        user_id: str, 
        space_id: str,
        messages: List[OpenAICompatibleMessage] = None,
        max_token_size: int = 4000,
    ) -> ContextData:
        """
        Retrieves formatted user context (profiles + relevant events) for LLM prompts.
        """
        promise = await get_user_context(
            user_id=user_id,
            project_id=space_id,
            max_token_size=max_token_size,
            prefer_topics=[],
            only_topics=[],
            max_subtopic_size=5,
            topic_limits={},
            profile_event_ratio=0.5,
            require_event_summary=True,
            chats=messages or [],
            event_similarity_threshold=0.5,
            time_range_in_days=30,
        )
        return cls._unwrap(promise)

    @classmethod
    async def search_memories(
        cls, 
        user_id: str, 
        space_id: str, 
        query: str, 
        topk: int = 10,
        similarity_threshold: float = 0.5
    ) -> UserEventGistsData:
        """
        Directly searches for relevant event memories using vector similarity.
        """
        promise = await search_user_event_gists(
            user_id=user_id,
            project_id=space_id,
            query=query,
            topk=topk,
            similarity_threshold=similarity_threshold,
            time_range_in_days=365,
        )
        return cls._unwrap(promise)

    @classmethod
    async def get_recent_memories(
        cls, user_id: str, space_id: str, topk: int = 10
    ) -> UserEventGistsData:
        """
        Lists the most recent event memories.
        """
        promise = await get_user_event_gists(
            user_id=user_id, project_id=space_id, topk=topk, time_range_in_days=30
        )
        return cls._unwrap(promise)

    # --- Ingestion ---

    @classmethod
    async def insert_chat(
        cls, 
        user_id: str, 
        space_id: str, 
        messages: List[OpenAICompatibleMessage]
    ) -> IdData:
        """
        Inserts a chat record into the buffer for memory processing.
        """
        chat_blob = ChatBlob(messages=messages)
        blob_data = BlobData(
            blob_type=BlobType.chat,
            blob_data=chat_blob.get_blob_data()
        )
        promise = await insert_blob(
            user_id=user_id, 
            project_id=space_id, 
            blob=blob_data
        )
        return cls._unwrap(promise)

    @classmethod
    async def trigger_buffer_flush(
        cls, user_id: str, space_id: str, blob_type: BlobType = BlobType.chat
    ) -> None:
        """
        Manually triggers the processing of pending data in the buffer.
        """
        promise = await flush_buffer(
            user_id=user_id, project_id=space_id, blob_type=blob_type
        )
        cls._unwrap(promise)
