from sqlalchemy.orm import Session
from typing import List, Optional
from app.models.persona import Persona
from app.schemas.persona import PersonaCreate, PersonaUpdate

def get_persona(db: Session, persona_id: int) -> Optional[Persona]:
    return db.query(Persona).filter(Persona.id == persona_id, Persona.deleted == False).first()

def get_personas(db: Session, skip: int = 0, limit: int = 100) -> List[Persona]:
    return db.query(Persona).filter(Persona.deleted == False).offset(skip).limit(limit).all()

def create_persona(db: Session, persona: PersonaCreate) -> Persona:
    db_persona = Persona(
        name=persona.name,
        description=persona.description,
        system_prompt=persona.system_prompt,
        is_preset=persona.is_preset
    )
    db.add(db_persona)
    db.commit()
    db.refresh(db_persona)
    return db_persona

def update_persona(db: Session, persona_id: int, persona_in: PersonaUpdate) -> Optional[Persona]:
    db_persona = get_persona(db, persona_id)
    if not db_persona:
        return None
    
    update_data = persona_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_persona, field, value)
    
    db.add(db_persona)
    db.commit()
    db.refresh(db_persona)
    return db_persona

def delete_persona(db: Session, persona_id: int) -> bool:
    db_persona = get_persona(db, persona_id)
    if not db_persona:
        return False
    
    # 逻辑删除
    db_persona.deleted = True
    db.add(db_persona)
    db.commit()
    return True
