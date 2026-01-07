import asyncio
import logging
from typing import List, Optional, Dict, Any
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.llm import LLMConfig
from app.models.embedding import EmbeddingSetting
from app.vendor.memobase_server.connectors import init_db, Session
from app.vendor.memobase_server.env import reinitialize_config, CONFIG
from app.vendor.memobase_server.controllers.buffer_background import start_memobase_worker
from app.vendor.memobase_server.models.database import UserEvent, UserEventGist
from app.vendor.memobase_server.utils import to_uuid
from app.vendor.memobase_server.llms.embeddings import get_embedding
from sqlalchemy import text, desc, select, func
from datetime import datetime, timedelta

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
from app.vendor.memobase_server.controllers.event_gist import serialize_embedding
from app.vendor.memobase_server.controllers.buffer import flush_buffer, insert_blob_to_buffer
from app.vendor.memobase_server.controllers.project import (
    get_project_profile_config_string, 
    update_project_profile_config
)

# SDK Models
from app.vendor.memobase_server.models.response import (
    UserProfilesData, ContextData, IdData, UserData, UserEventGistsData, IdsData, UserEventsData, ProfileConfigData,
    EventGistData, UserEventGistData
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


def reload_sdk_config():
    """
    Reloads Memobase SDK configuration from Database (priority) or Environment.
    """
    # 1. Map main app settings to Memobase config
    
    # Load defaults from Environment Variables (settings)
    llm_api_key = settings.MEMOBASE_LLM_API_KEY
    llm_base_url = settings.MEMOBASE_LLM_BASE_URL
    best_llm_model = settings.MEMOBASE_BEST_LLM_MODEL
    
    embedding_provider = settings.MEMOBASE_EMBEDDING_PROVIDER
    embedding_api_key = settings.MEMOBASE_EMBEDDING_API_KEY
    embedding_base_url = settings.MEMOBASE_EMBEDDING_BASE_URL
    embedding_model = settings.MEMOBASE_EMBEDDING_MODEL
    embedding_dim = settings.MEMOBASE_EMBEDDING_DIM

    # Override with Database Configurations if available
    try:
        # Use a new session scope
        with SessionLocal() as db:
            # 1.1 LLM Config
            llm_config_db = db.query(LLMConfig).filter(LLMConfig.deleted == False).first()
            if llm_config_db:
                if llm_config_db.api_key: llm_api_key = llm_config_db.api_key
                if llm_config_db.base_url: llm_base_url = llm_config_db.base_url
                if llm_config_db.model_name: best_llm_model = llm_config_db.model_name
            
            # 1.2 Embedding Config
            embedding_config_db = db.query(EmbeddingSetting).filter(EmbeddingSetting.deleted == False).first()
            if embedding_config_db:
                if embedding_config_db.embedding_provider: embedding_provider = embedding_config_db.embedding_provider
                if embedding_config_db.embedding_api_key: embedding_api_key = embedding_config_db.embedding_api_key
                if embedding_config_db.embedding_base_url: embedding_base_url = embedding_config_db.embedding_base_url
                if embedding_config_db.embedding_model: embedding_model = embedding_config_db.embedding_model
                if embedding_config_db.embedding_dim is not None: embedding_dim = embedding_config_db.embedding_dim
                
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.warning(f"Error loading Memobase config from DB: {e}. Using environment defaults.")

    memo_config = {
        "llm_api_key": llm_api_key,
        "llm_base_url": llm_base_url,
        "best_llm_model": best_llm_model,
        "language": settings.MEMOBASE_LANGUAGE,
        "enable_event_embedding": settings.MEMOBASE_ENABLE_EVENT_EMBEDDING,
        "embedding_provider": embedding_provider,
        "embedding_api_key": embedding_api_key,
        "embedding_base_url": embedding_base_url,
        "embedding_model": embedding_model,
        "embedding_dim": embedding_dim,
    }
    
    # 2. Reinitialize the global CONFIG object in SDK
    reinitialize_config(memo_config)
    return memo_config


async def initialize_memo_sdk():
    """
    Initialize the Memobase SDK with settings from the main app.
    """
    # 1. Load and apply config
    reload_sdk_config()
    
    # 2. Initialize Database
    init_db(settings.MEMOBASE_DB_URL)
    
    # 3. Perform Sanity Checks (Optional but recommended)
    logger = logging.getLogger(__name__)
    try:
        await check_embedding_sanity()
        await llm_sanity_check()
        logger.info("Memobase SDK sanity checks passed.")
    except Exception as e:
        # Log warning but don't fail - allows graceful degradation
        logger.warning(f"Memobase SDK Sanity Check Failed: {e}. Memory features may not work correctly.")
    
    # 4. Start background worker
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
        messages: List[OpenAICompatibleMessage],
        fields: dict = None
    ) -> IdData:
        """
        Inserts a chat record into the buffer for memory processing.
        
        Args:
            user_id: User identifier
            space_id: Space/project identifier
            messages: Chat messages in OpenAI format
            fields: Optional metadata (e.g., friend_id, session_id, archived_at)
        """
        chat_blob = ChatBlob(messages=messages)
        blob_data = BlobData(
            blob_type=BlobType.chat,
            blob_data=chat_blob.get_blob_data(),
            fields=fields or {}
        )
        promise = await insert_blob(
            user_id=user_id, 
            project_id=space_id, 
            blob=blob_data
        )
        result = cls._unwrap(promise)
        
        # Also insert into buffer so that flush_buffer can find it
        buffer_promise = await insert_blob_to_buffer(
            user_id=user_id,
            project_id=space_id,
            blob_id=result.id,
            blob_data=blob_data.to_blob()
        )
        cls._unwrap(buffer_promise)
        
        return result

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

    # --- Project Config Management ---

    @classmethod
    async def get_profile_config(cls, space_id: str) -> ProfileConfigData:
        """
        Retrieves the profile configuration (YAML) for a given space.
        """
        promise = await get_project_profile_config_string(project_id=space_id)
        return cls._unwrap(promise)

    @classmethod
    async def update_profile_config(cls, space_id: str, profile_config: str) -> None:
        """
        Updates the profile configuration (YAML) for a given space.
        """
        promise = await update_project_profile_config(project_id=space_id, profile_config=profile_config)
        cls._unwrap(promise)

    @classmethod
    async def filter_friend_event_gists(
        cls, user_id: str, space_id: str, friend_id: int, topk: int = 50
    ) -> UserEventGistsData:
        """
        Filter event gists by friend_id tag.
        """
        user_id_uuid = to_uuid(user_id)
        # Use a safe time window (e.g., last 365 days)
        days_ago = datetime.utcnow() - timedelta(days=365)
        
        with Session() as session:
            # Query UserEventGist and join with UserEvent to filter by tags
            query = (
                session.query(UserEventGist)
                .join(UserEvent, UserEventGist.event_id == UserEvent.id)
                .filter(
                    UserEvent.user_id == user_id_uuid,
                    UserEvent.project_id == space_id,
                    UserEvent.created_at >= days_ago
                )
            )
            
            # Filter by exact tag-value pair (friend_id)
            # SQLite specific JSON filtering
            query = query.filter(text(
                """
                EXISTS (
                    SELECT 1 
                    FROM json_each(json_extract(user_events.event_data, '$.event_tags')) 
                    WHERE json_extract(value, '$.tag') = 'friend_id' 
                    AND json_extract(value, '$.value') = :friend_id
                )
                """
            ).params(friend_id=str(friend_id)))
            
            gists = query.order_by(desc(UserEventGist.created_at)).limit(topk).all()
            
            result_gists = [
                UserEventGistData(
                    id=g.id,
                    gist_data=EventGistData(**g.gist_data),
                    created_at=g.created_at,
                    updated_at=g.updated_at
                )
                for g in gists
            ]
            
            return UserEventGistsData(gists=result_gists, events=[])

    # --- Recall / Search Extensions ---

    @classmethod
    async def search_memories_with_tags(
        cls,
        user_id: str,
        space_id: str,
        query: str,
        friend_id: int,
        topk: int = 5,
        similarity_threshold: float = 0.5
    ) -> UserEventGistsData:
        """
        Search event gists using vector similarity with friend_id tag filtering.
        
        Args:
            user_id: User identifier
            space_id: Space/project identifier
            query: Query string to search
            friend_id: Friend ID to filter by (tag-based filtering)
            topk: Maximum number of results to return
            similarity_threshold: Minimum similarity score (0-1)
            
        Returns:
            UserEventGistsData with filtered event gists
        """
        logger = logging.getLogger(__name__)
        user_id_uuid = to_uuid(user_id)
        
        # 1. Check if event embedding is enabled
        if not CONFIG.enable_event_embedding:
            logger.warning("Event embedding is not enabled, falling back to filter_friend_event_gists")
            return await cls.filter_friend_event_gists(user_id, space_id, friend_id, topk)
        
        # 2. Get query embedding
        query_embeddings = await get_embedding(
            space_id, [query], phase="query", model=CONFIG.embedding_model
        )
        if not query_embeddings.ok():
            logger.error(f"Failed to get query embedding: {query_embeddings.msg()}")
            raise MemoServiceException(f"Failed to get query embedding: {query_embeddings.msg()}")
        
        query_embedding = query_embeddings.data()[0]
        query_embedding_bytes = serialize_embedding(query_embedding)
        
        # 3. Calculate time cutoff (365 days)
        days_ago = datetime.utcnow() - timedelta(days=365)
        
        # 4. Build SQL query with friend_id tag filter and vector similarity
        # sqlite-vec uses vec_distance_cosine
        distance_expr = func.vec_distance_cosine(UserEventGist.embedding, query_embedding_bytes)
        similarity_expr = 1 - distance_expr
        
        stmt = (
            select(
                UserEventGist,
                similarity_expr.label("similarity"),
            )
            .join(UserEvent, UserEventGist.event_id == UserEvent.id)
            .where(
                UserEvent.user_id == user_id_uuid,
                UserEvent.project_id == space_id,
                UserEvent.created_at >= days_ago,
                (1 - distance_expr) > similarity_threshold,
                UserEventGist.embedding.is_not(None),
            )
            # Add friend_id tag filter using json_each
            .where(text("""
                EXISTS (
                    SELECT 1 
                    FROM json_each(json_extract(user_events.event_data, '$.event_tags')) 
                    WHERE json_extract(value, '$.tag') = 'friend_id' 
                    AND json_extract(value, '$.value') = :friend_id
                )
            """).bindparams(friend_id=str(friend_id)))
            .order_by(desc("similarity"))
            .limit(topk)
        )
        
        with Session() as session:
            result = session.execute(stmt).all()
            result_gists = []
            for row in result:
                gist: UserEventGist = row[0]
                similarity: float = row[1]
                result_gists.append(
                    UserEventGistData(
                        id=gist.id,
                        gist_data=EventGistData(**gist.gist_data),
                        created_at=gist.created_at,
                        updated_at=gist.updated_at,
                        similarity=similarity,
                    )
                )
        
        logger.debug(f"search_memories_with_tags returned {len(result_gists)} gists for friend {friend_id}")
        return UserEventGistsData(gists=result_gists, events=[])

    @classmethod
    async def recall_memory(
        cls,
        user_id: str,
        space_id: str,
        query: str,
        friend_id: int,
        topk_event: int = 5,
        threshold: float = 0.5,
        timeout: float = 3.0
    ) -> Dict[str, Any]:
        """
        Unified memory recall interface that retrieves relevant events only.
        
        Args:
            user_id: User identifier
            space_id: Space/project identifier
            query: Query string to search
            friend_id: Friend ID for event filtering
            topk_event: Max events to return
            threshold: Similarity threshold for event search
            timeout: Maximum time (seconds) to wait for both searches
            
        Returns:
            Dictionary with format:
            {
                "events": [{"date": ..., "content": ...}, ...]
            }
        """
        logger = logging.getLogger(__name__)
        
        events_result = []
        
        try:
            events_task = cls.search_memories_with_tags(
                user_id, space_id, query, friend_id, topk_event, threshold
            )
            events_data = await asyncio.wait_for(
                asyncio.gather(events_task),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            logger.warning(f"recall_memory timed out after {timeout}s")
            return {"events": []}
        except Exception as e:
            logger.error(f"recall_memory failed: {e}")
            raise MemoServiceException(f"Memory recall failed: {e}") from e
        
        events_data = events_data[0] if events_data else UserEventGistsData(gists=[], events=[])

        # Format events
        for gist in events_data.gists:
            gist_data = gist.gist_data if isinstance(gist.gist_data, dict) else gist.gist_data.model_dump()
            events_result.append({
                "date": gist.created_at.isoformat() if gist.created_at else None,
                "content": gist_data.get("summary", gist_data.get("content", "")),
                "similarity": getattr(gist, 'similarity', None)
            })
        
        logger.info(f"recall_memory: {len(events_result)} events for query: {query[:30]}...")
        
        return {
            "events": events_result
        }

