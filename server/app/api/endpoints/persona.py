from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.api import deps
from app.schemas import persona as persona_schemas
from app.services import persona_service

router = APIRouter()

@router.get("/", response_model=List[persona_schemas.Persona])
def read_personas(
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
):
    """
    Retrieve personas.
    """
    personas = persona_service.get_personas(db, skip=skip, limit=limit)
    return personas

@router.post("/", response_model=persona_schemas.Persona)
def create_persona(
    *,
    db: Session = Depends(deps.get_db),
    persona_in: persona_schemas.PersonaCreate,
):
    """
    Create new persona.
    """
    persona = persona_service.create_persona(db, persona=persona_in)
    return persona

@router.get("/{persona_id}", response_model=persona_schemas.Persona)
def read_persona(
    *,
    db: Session = Depends(deps.get_db),
    persona_id: int,
):
    """
    Get persona by ID.
    """
    persona = persona_service.get_persona(db, persona_id=persona_id)
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")
    return persona

@router.put("/{persona_id}", response_model=persona_schemas.Persona)
def update_persona(
    *,
    db: Session = Depends(deps.get_db),
    persona_id: int,
    persona_in: persona_schemas.PersonaUpdate,
):
    """
    Update a persona.
    """
    persona = persona_service.update_persona(db, persona_id=persona_id, persona_in=persona_in)
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")
    return persona

@router.delete("/{persona_id}", response_model=persona_schemas.Persona)
def delete_persona(
    *,
    db: Session = Depends(deps.get_db),
    persona_id: int,
):
    """
    Delete a persona.
    """
    persona = persona_service.get_persona(db, persona_id=persona_id)
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")
    
    success = persona_service.delete_persona(db, persona_id=persona_id)
    if not success:
         raise HTTPException(status_code=500, detail="Failed to delete persona")
         
    return persona
