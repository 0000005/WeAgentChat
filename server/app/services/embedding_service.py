from sqlalchemy.orm import Session
from typing import List, Optional
from sqlalchemy import func
from app.models.embedding import EmbeddingSetting
from app.schemas.embedding import EmbeddingSettingCreate, EmbeddingSettingUpdate
from app.services.settings_service import SettingsService

class EmbeddingService:
    _provider_labels = {
        "openai": "OpenAI",
        "jina": "Jina",
        "lmstudio": "LMStudio",
        "ollama": "Ollama",
    }

    @staticmethod
    def _normalize_config_name(
        db: Session,
        provider: Optional[str],
        config_name: Optional[str],
        exclude_id: Optional[int] = None,
    ) -> str:
        base = (config_name or "").strip()
        if not base:
            base = EmbeddingService._provider_labels.get(provider or "", "Embedding")

        existing_query = db.query(EmbeddingSetting.config_name).filter(EmbeddingSetting.deleted == False)
        if exclude_id is not None:
            existing_query = existing_query.filter(EmbeddingSetting.id != exclude_id)
        existing_names = {row[0] for row in existing_query.all() if row[0]}

        if base not in existing_names:
            return base

        suffix = 2
        while f"{base} #{suffix}" in existing_names:
            suffix += 1
        return f"{base} #{suffix}"

    @staticmethod
    def get_setting(db: Session, setting_id: int) -> Optional[EmbeddingSetting]:
        return db.query(EmbeddingSetting).filter(EmbeddingSetting.id == setting_id, EmbeddingSetting.deleted == False).first()

    @staticmethod
    def get_active_setting(db: Session) -> Optional[EmbeddingSetting]:
        active_id = SettingsService.get_setting(db, "memory", "active_embedding_config_id", None)
        if active_id is None:
            return None
        return EmbeddingService.get_setting(db, active_id)

    @staticmethod
    def get_multi(db: Session, skip: int = 0, limit: int = 100) -> List[EmbeddingSetting]:
        return (
            db.query(EmbeddingSetting)
            .filter(EmbeddingSetting.deleted == False)
            .order_by(EmbeddingSetting.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    @staticmethod
    def count_settings(db: Session) -> int:
        return (
            db.query(func.count(EmbeddingSetting.id))
            .filter(EmbeddingSetting.deleted == False)
            .scalar()
            or 0
        )

    @staticmethod
    def create_setting(db: Session, obj_in: EmbeddingSettingCreate) -> EmbeddingSetting:
        data = obj_in.model_dump()
        data["config_name"] = EmbeddingService._normalize_config_name(
            db, data.get("embedding_provider"), data.get("config_name")
        )
        db_obj = EmbeddingSetting(**data)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    @staticmethod
    def update_setting(db: Session, db_obj: EmbeddingSetting, obj_in: EmbeddingSettingUpdate) -> EmbeddingSetting:
        update_data = obj_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if field == "config_name" and value is not None and not value.strip():
                value = None
            setattr(db_obj, field, value)

        db_obj.config_name = EmbeddingService._normalize_config_name(
            db,
            db_obj.embedding_provider,
            db_obj.config_name,
            exclude_id=db_obj.id,
        )
        
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    @staticmethod
    def delete_setting(db: Session, db_obj: EmbeddingSetting) -> EmbeddingSetting:
        # Soft delete
        db_obj.deleted = True
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

embedding_service = EmbeddingService()
