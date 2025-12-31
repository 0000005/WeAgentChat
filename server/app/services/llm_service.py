from sqlalchemy.orm import Session
from app.models.llm import LLMConfig
from app.schemas.llm import LLMConfigUpdate, LLMConfigCreate

class LLMService:
    @staticmethod
    def get_config(db: Session) -> LLMConfig:
        """
        Get the current active LLM configuration.
        We assume a single configuration pattern for now (taking the first non-deleted one).
        """
        return db.query(LLMConfig).filter(LLMConfig.deleted == False).first()

    @staticmethod
    def update_config(db: Session, config_in: LLMConfigUpdate) -> LLMConfig:
        """
        Update the LLM configuration. If none exists, create one.
        """
        existing_config = db.query(LLMConfig).filter(LLMConfig.deleted == False).first()

        if existing_config:
            # Update existing
            update_data = config_in.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                setattr(existing_config, field, value)
            
            db.add(existing_config)
            db.commit()
            db.refresh(existing_config)
            return existing_config
        else:
            # Create new
            new_config = LLMConfig(**config_in.model_dump())
            db.add(new_config)
            db.commit()
            db.refresh(new_config)
            return new_config

llm_service = LLMService()
