"""
Initialize logger, encoder, and config.
"""

import os
import datetime
import json
import yaml
import logging
import tiktoken
import dataclasses
from dataclasses import dataclass, field
from typing import Optional, Literal, Union
from dotenv import load_dotenv
from zoneinfo import ZoneInfo
from datetime import timezone
from typeguard import check_type
import structlog
from .types import UserProfileTopic
from .struct_logger import ProjectStructLogger, configure_logger

load_dotenv()


class BillingStatus:
    free = "free"
    pro = "pro"
    usage_based = "usage_based"


BILLING_REFILL_AMOUNT_MAP = {
    BillingStatus.free: int(os.getenv("USAGE_TOKEN_LIMIT_ACTIVE", 0)) or None,
}


class ProjectStatus:
    ultra = "ultra"
    pro = "pro"
    active = "active"
    suspended = "suspended"


USAGE_TOKEN_LIMIT_MAP = {
    ProjectStatus.active: int(os.getenv("USAGE_TOKEN_LIMIT_ACTIVE", -1)),
    ProjectStatus.pro: int(os.getenv("USAGE_TOKEN_LIMIT_PRO", -1)),
    ProjectStatus.ultra: int(os.getenv("USAGE_TOKEN_LIMIT_ULTRA", -1)),
}


class ContanstTable:
    topic = "topic"
    sub_topic = "sub_topic"
    memo = "memo"
    update_hits = "update_hits"

    roleplay_plot_status = "roleplay_plot_status"


class BufferStatus:
    idle = "idle"
    processing = "processing"
    done = "done"
    failed = "failed"


class TelemetryKeyName:
    insert_blob_request = "insert_blob_request"
    insert_blob_success_request = "insert_blob_success_request"
    llm_input_tokens = "llm_input_tokens"
    llm_output_tokens = "llm_output_tokens"
    has_request = "has_request"


@dataclass
class Config:
    # IMPORTANT!
    persistent_chat_blobs: bool = False
    use_timezone: Optional[
        Literal[
            "UTC", "America/New_York", "Europe/London", "Asia/Tokyo", "Asia/Shanghai"
        ]
    ] = None

    system_prompt: str = None
    buffer_flush_interval: int = 60 * 60  # 1 hour
    max_chat_blob_buffer_token_size: int = 1024
    max_chat_blob_buffer_process_token_size: int = 16384
    max_profile_subtopics: int = 15
    max_pre_profile_token_size: int = 128
    llm_tab_separator: str = "::"
    cache_user_profiles_ttl: int = 60 * 20  # 20 minutes

    # LLM
    language: Literal["en", "zh"] = "en"
    llm_style: Literal["openai", "doubao_cache"] = "openai"
    llm_base_url: str = None
    llm_api_key: str = None
    llm_openai_default_query: dict[str, str] = None
    llm_openai_default_header: dict[str, str] = None
    best_llm_model: str = "gpt-4o-mini"
    thinking_llm_model: str = "o4-mini"
    summary_llm_model: str = None

    enable_event_embedding: bool = True
    embedding_provider: Literal["openai", "jina", "ollama"] = "openai"
    embedding_api_key: str = None
    embedding_base_url: str = None
    embedding_dim: int = 1536
    embedding_model: str = "text-embedding-3-small"
    embedding_max_token_size: int = 8192

    additional_user_profiles: list[dict] = field(default_factory=list)
    overwrite_user_profiles: Optional[list[dict]] = None
    event_theme_requirement: Optional[str] = (
        "Focus on the user's infos, not its instructions."
    )
    profile_strict_mode: bool = False
    profile_validate_mode: bool = True

    minimum_chats_token_size_for_event_summary: int = 256
    event_tags: list[dict] = field(default_factory=list)
    # Telemetry
    telemetry_deployment_environment: str = "local"

    @classmethod
    def _process_env_vars(cls, config_dict):
        """
        Process all environment variables for the config class.

        Args:
            cls: The config class
            config_dict: The current configuration dictionary

        Returns:
            Updated configuration dictionary with environment variables applied
        """
        # Ensure we have a dictionary to work with
        if not isinstance(config_dict, dict):
            config_dict = {}

        for field in dataclasses.fields(cls):
            field_name = field.name
            field_type = field.type
            env_var_name = f"MEMOBASE_{field_name.upper()}"
            if env_var_name in os.environ:
                env_value = os.environ[env_var_name]

                # Try to parse as JSON first
                try:
                    parsed_value = json.loads(env_value)
                    # Check if parsed value matches the type
                    try:
                        check_type(parsed_value, field_type)
                        config_dict[field_name] = parsed_value
                        continue
                    except TypeError:
                        # Parsed value doesn't match type, fall through to try raw string
                        pass
                except json.JSONDecodeError:
                    # Not valid JSON, fall through to try raw string
                    pass

                # Try the raw string
                try:
                    check_type(env_value, field_type)
                    config_dict[field_name] = env_value
                except TypeError as e:
                    LOG.warning(
                        f"Value for {env_var_name} is not compatible with field type {field_type}. Ignoring."
                    )

        return config_dict

    @classmethod
    def load_config(cls, config_dict: dict = None) -> "Config":
        """
        Load configuration with the following priority:
        1. config_dict (if provided)
        2. Environment variables (MEMOBASE_*)
        3. config.yaml (if exists)
        4. Default values
        """
        final_config_dict = {}
        
        # 1. Load from config.yaml if it exists
        if os.path.exists("config.yaml"):
            try:
                with open("config.yaml") as f:
                    file_config = yaml.safe_load(f)
                    if file_config:
                        final_config_dict.update(file_config)
                        LOG.info("Loaded config from ./config.yaml")
            except Exception as e:
                LOG.warning(f"Failed to load config.yaml: {e}")

        # 2. Process environment variables (overrides file)
        final_config_dict = cls._process_env_vars(final_config_dict)

        # 3. Apply provided config_dict (overrides environment)
        if config_dict:
            final_config_dict.update(config_dict)

        # Filter out any keys that aren't in the dataclass
        fields = {field.name for field in dataclasses.fields(cls)}
        filtered_config = {k: v for k, v in final_config_dict.items() if k in fields}
        
        config_obj = cls(**filtered_config)
        # LOG.info(f"Configuration initialized: {config_obj}")
        return config_obj

    def validate(self):
        """Validate the configuration when the SDK is actually started."""
        assert self.llm_api_key is not None, "llm_api_key is required"
        if self.enable_event_embedding:
            assert (
                self.embedding_api_key is not None
            ), "embedding_api_key is required for event embedding"

            if self.embedding_provider == "jina":
                assert self.embedding_model in {
                    "jina-embeddings-v3",
                }, "embedding_model must be one of the following: jina-embeddings-v3"

    def __post_init__(self):
        # We handle default value assignment for embedding_api_key here
        # but defer strict assertions to validate()
        if self.enable_event_embedding:
            if self.embedding_api_key is None and (
                self.llm_style == self.embedding_provider == "openai"
                and self.llm_api_key is not None
            ):
                # default to llm config if embedding_api_key is not set
                self.embedding_api_key = self.llm_api_key
                self.embedding_base_url = self.llm_base_url

        if self.additional_user_profiles:
            [UserProfileTopic(**up) for up in self.additional_user_profiles]
        if self.overwrite_user_profiles:
            [UserProfileTopic(**up) for up in self.overwrite_user_profiles]

    @property
    def timezone(self) -> timezone:
        if self.use_timezone is None:
            return datetime.datetime.now().astimezone().tzinfo

        # For named timezones, we need to use the datetime.timezone.ZoneInfo
        return ZoneInfo(self.use_timezone)


@dataclass
class ProfileConfig:
    language: Literal["en", "zh"] = None
    profile_strict_mode: bool | None = None
    profile_validate_mode: bool | None = None
    additional_user_profiles: list[dict] = field(default_factory=list)
    overwrite_user_profiles: Optional[list[dict]] = None
    event_theme_requirement: Optional[str] = None

    event_tags: list[dict] = None

    def __post_init__(self):
        if self.language not in ["en", "zh"]:
            self.language = None
        if self.additional_user_profiles:
            [UserProfileTopic(**up) for up in self.additional_user_profiles]
        if self.overwrite_user_profiles:
            [UserProfileTopic(**up) for up in self.overwrite_user_profiles]

    @classmethod
    def load_config_string(cls, config_string: str) -> "Config":
        overwrite_config = yaml.safe_load(config_string)
        if overwrite_config is None:
            return cls()
        # Get all field names from the dataclass
        fields = {field.name for field in dataclasses.fields(cls)}
        # Filter out any keys from overwrite_config that aren't in the dataclass
        filtered_config = {k: v for k, v in overwrite_config.items() if k in fields}
        overwrite_config = cls(**filtered_config)
        return overwrite_config


class Colors:
    BLUE = "\033[94m"
    BOLD = "\033[1m"
    GREEN = "\033[92m"
    END = "\033[0m"


# 使用主项目的日志配置，不再干扰全局日志设置
# 注意：不要清除 uvicorn 的 handler，也不要添加独立的 handler
LOG = logging.getLogger("memobase_server")


try:
    ENCODER = tiktoken.encoding_for_model("gpt-4o")
except Exception as e:
    # Some bundled environments may miss the newest tiktoken encoding assets;
    # fall back to a compatible tokenizer so the server can still start.
    LOG.warning(f"Failed to load gpt-4o encoder ({e}); falling back to cl100k_base")
    try:
        ENCODER = tiktoken.get_encoding("cl100k_base")
    except Exception as e2:
        # If even cl100k assets are unavailable (e.g., offline + no cached files),
        # fall back to a minimal encoder to keep the service running.
        LOG.warning(f"Failed to load cl100k_base encoder ({e2}); using DummyEncoder")

        class DummyEncoder:
            def encode(self, text: str):
                # Simple UTF-8 byte list as tokens; good enough for length estimates.
                return list(text.encode("utf-8"))

            def decode(self, tokens):
                try:
                    return bytes(tokens).decode("utf-8")
                except Exception:
                    return ""

        ENCODER = DummyEncoder()

CONFIG = Config.load_config()


def reinitialize_config(config_dict: dict = None):
    """Reinitialize the global CONFIG object with new parameters."""
    global CONFIG
    new_config = Config.load_config(config_dict)
    
    # Mutate the existing CONFIG object fields to ensure all modules holding a reference to it see the changes
    for field in dataclasses.fields(Config):
        setattr(CONFIG, field.name, getattr(new_config, field.name))
    
    # Reset cached LLM/Embedding clients to ensure they are recreated with new config
    try:
        from .llms.utils import reset_clients as reset_llm_clients
        from .llms.embeddings.utils import reset_clients as reset_embedding_clients
        reset_llm_clients()
        reset_embedding_clients()
    except ImportError:
        # Ignore if modules are not yet loaded or have circular issues
        pass
        
    return CONFIG


class ProjectLogger:
    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def debug(self, project_id: str, user_id: str, message: str):
        self.logger.debug(
            json.dumps({"project_id": str(project_id), "user_id": str(user_id)})
            + " | "
            + message
        )

    def info(self, project_id: str, user_id: str, message: str):
        self.logger.info(
            json.dumps({"project_id": str(project_id), "user_id": str(user_id)})
            + " | "
            + message
        )

    def warning(self, project_id: str, user_id: str, message: str):
        self.logger.warning(
            json.dumps({"project_id": str(project_id), "user_id": str(user_id)})
            + " | "
            + message
        )

    def error(
        self, project_id: str, user_id: str, message: str, exc_info: bool = False
    ):
        self.logger.error(
            json.dumps({"project_id": str(project_id), "user_id": str(user_id)})
            + " | "
            + message,
            exc_info=exc_info,
        )


# 统一使用 ProjectLogger（主项目不使用 structlog JSON 格式）
TRACE_LOG = ProjectLogger(LOG)
