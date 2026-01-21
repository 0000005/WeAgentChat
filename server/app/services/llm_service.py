from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.llm import LLMConfig
from app.schemas.llm import LLMConfigUpdate, LLMConfigCreate
from app.services.settings_service import SettingsService

class LLMService:
    _provider_labels = {
        "openai": "OpenAI",
        "zhipu": "Zhipu",
        "modelscope": "ModelScope",
        "minimax": "MiniMax",
        "openai_compatible": "OpenAI Compatible",
    }

    @staticmethod
    def normalize_model_name(model_name: str | None) -> str | None:
        """
        Normalize model name for agents MultiProvider.
        SilliconFlow uses "Pro/..." model names; force OpenAI provider prefix.
        """
        if not model_name:
            return model_name
        if model_name.startswith("Pro/"):
            return f"openai/{model_name}"
        return model_name

    @staticmethod
    def _normalize_config_name(
        db: Session,
        provider: Optional[str],
        config_name: Optional[str],
        exclude_id: Optional[int] = None,
    ) -> str:
        base = (config_name or "").strip()
        if not base:
            base = LLMService._provider_labels.get(provider or "", "LLM")

        existing_query = db.query(LLMConfig.config_name).filter(LLMConfig.deleted == False)
        if exclude_id is not None:
            existing_query = existing_query.filter(LLMConfig.id != exclude_id)
        existing_names = {row[0] for row in existing_query.all() if row[0]}

        if base not in existing_names:
            return base

        suffix = 2
        while f"{base} #{suffix}" in existing_names:
            suffix += 1
        return f"{base} #{suffix}"

    @staticmethod
    def get_config(db: Session) -> Optional[LLMConfig]:
        """
        Backward-compatible: return active LLM configuration if available.
        """
        return LLMService.get_active_config(db)

    @staticmethod
    def get_config_by_id(db: Session, config_id: int) -> Optional[LLMConfig]:
        return (
            db.query(LLMConfig)
            .filter(LLMConfig.id == config_id, LLMConfig.deleted == False)
            .first()
        )

    @staticmethod
    def get_multi(db: Session, skip: int = 0, limit: int = 100) -> List[LLMConfig]:
        return (
            db.query(LLMConfig)
            .filter(LLMConfig.deleted == False)
            .order_by(LLMConfig.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    @staticmethod
    def count_configs(db: Session) -> int:
        return (
            db.query(func.count(LLMConfig.id))
            .filter(LLMConfig.deleted == False)
            .scalar()
            or 0
        )

    @staticmethod
    def get_active_config(db: Session) -> Optional[LLMConfig]:
        active_id = SettingsService.get_setting(db, "chat", "active_llm_config_id", None)
        if active_id is None:
            return None
        return LLMService.get_config_by_id(db, active_id)

    @staticmethod
    def create_config(db: Session, config_in: LLMConfigCreate) -> LLMConfig:
        data = config_in.model_dump()
        data["config_name"] = LLMService._normalize_config_name(
            db, data.get("provider"), data.get("config_name")
        )
        db_obj = LLMConfig(**data)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    @staticmethod
    def update_config(db: Session, config_id: int, config_in: LLMConfigUpdate) -> Optional[LLMConfig]:
        """
        Update an existing LLM configuration.
        """
        existing_config = LLMService.get_config_by_id(db, config_id)
        if not existing_config:
            return None

        update_data = config_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if field == "config_name" and value is not None and not value.strip():
                value = None
            setattr(existing_config, field, value)

        existing_config.config_name = LLMService._normalize_config_name(
            db,
            existing_config.provider,
            existing_config.config_name,
            exclude_id=existing_config.id,
        )

        db.add(existing_config)
        db.commit()
        db.refresh(existing_config)
        return existing_config

    @staticmethod
    def delete_config(db: Session, db_obj: LLMConfig) -> LLMConfig:
        db_obj.deleted = True
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

llm_service = LLMService()
