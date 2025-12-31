from fastapi.testclient import TestClient
from app.core.config import settings

def test_create_persona(client: TestClient):
    """
    Test creating a new persona.
    """
    data = {
        "name": "Test Persona",
        "description": "A persona for testing.",
        "system_prompt": "You are a test bot.",
        "is_preset": False
    }
    response = client.post(f"{settings.API_STR}/personas/", json=data)
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == data["name"]
    assert content["description"] == data["description"]
    assert content["system_prompt"] == data["system_prompt"]
    assert content["is_preset"] == data["is_preset"]
    assert "id" in content

def test_read_personas(client: TestClient):
    """
    Test reading the list of personas.
    """
    # Create a persona first to ensure there's something to read
    client.post(f"{settings.API_STR}/personas/", json={
        "name": "List Test Persona",
        "description": "Testing list",
        "system_prompt": "List me",
        "is_preset": False
    })
    
    response = client.get(f"{settings.API_STR}/personas/")
    assert response.status_code == 200
    content = response.json()
    assert isinstance(content, list)
    assert len(content) >= 1

def test_read_persona(client: TestClient):
    """
    Test reading a single persona by ID.
    """
    # Create
    create_res = client.post(f"{settings.API_STR}/personas/", json={
        "name": "Single Test Persona",
        "description": "Testing single read",
        "system_prompt": "Read me",
        "is_preset": False
    })
    persona_id = create_res.json()["id"]

    # Read
    response = client.get(f"{settings.API_STR}/personas/{persona_id}")
    assert response.status_code == 200
    content = response.json()
    assert content["id"] == persona_id
    assert content["name"] == "Single Test Persona"

def test_read_persona_not_found(client: TestClient):
    """
    Test reading a non-existent persona.
    """
    response = client.get(f"{settings.API_STR}/personas/999999")
    assert response.status_code == 404

def test_update_persona(client: TestClient):
    """
    Test updating a persona.
    """
    # Create
    create_res = client.post(f"{settings.API_STR}/personas/", json={
        "name": "Update Test Persona",
        "description": "Before update",
        "system_prompt": "Old prompt",
        "is_preset": False
    })
    persona_id = create_res.json()["id"]

    # Update
    update_data = {
        "name": "Updated Persona Name",
        "system_prompt": "New prompt"
    }
    response = client.put(f"{settings.API_STR}/personas/{persona_id}", json=update_data)
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == "Updated Persona Name"
    assert content["system_prompt"] == "New prompt"
    assert content["description"] == "Before update" # Should remain unchanged

def test_delete_persona(client: TestClient):
    """
    Test deleting a persona.
    """
    # Create
    create_res = client.post(f"{settings.API_STR}/personas/", json={
        "name": "Delete Test Persona",
        "description": "To be deleted",
        "system_prompt": "Bye bye",
        "is_preset": False
    })
    persona_id = create_res.json()["id"]

    # Delete
    response = client.delete(f"{settings.API_STR}/personas/{persona_id}")
    assert response.status_code == 200
    
    # Verify it's gone (or at least not retrievable via get)
    get_res = client.get(f"{settings.API_STR}/personas/{persona_id}")
    assert get_res.status_code == 404
