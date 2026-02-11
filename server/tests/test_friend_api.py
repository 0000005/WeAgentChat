from fastapi.testclient import TestClient
from app.core.config import settings

def test_create_friend(client: TestClient):
    """
    Test creating a new friend.
    """
    data = {
        "name": "Test Friend",
        "description": "A friend for testing.",
        "system_prompt": "You are a test bot.",
        "is_preset": False
    }
    response = client.post(f"{settings.API_STR}/friends/", json=data)
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == data["name"]
    assert content["description"] == data["description"]
    assert content["system_prompt"] == data["system_prompt"]
    assert content["is_preset"] == data["is_preset"]
    assert content["enable_voice"] is False
    assert content["voice_id"] is None
    assert "id" in content

def test_read_friends(client: TestClient):
    """
    Test reading the list of friends.
    """
    # Create a friend first to ensure there's something to read
    client.post(f"{settings.API_STR}/friends/", json={
        "name": "List Test Friend",
        "description": "Testing list",
        "system_prompt": "List me",
        "is_preset": False
    })
    
    response = client.get(f"{settings.API_STR}/friends/")
    assert response.status_code == 200
    content = response.json()
    assert isinstance(content, list)
    assert len(content) >= 1

def test_read_friend(client: TestClient):
    """
    Test reading a single friend by ID.
    """
    # Create
    create_res = client.post(f"{settings.API_STR}/friends/", json={
        "name": "Single Test Friend",
        "description": "Testing single read",
        "system_prompt": "Read me",
        "is_preset": False
    })
    friend_id = create_res.json()["id"]

    # Read
    response = client.get(f"{settings.API_STR}/friends/{friend_id}")
    assert response.status_code == 200
    content = response.json()
    assert content["id"] == friend_id
    assert content["name"] == "Single Test Friend"

def test_read_friend_not_found(client: TestClient):
    """
    Test reading a non-existent friend.
    """
    response = client.get(f"{settings.API_STR}/friends/999999")
    assert response.status_code == 404

def test_update_friend(client: TestClient):
    """
    Test updating a friend.
    """
    # Create
    create_res = client.post(f"{settings.API_STR}/friends/", json={
        "name": "Update Test Friend",
        "description": "Before update",
        "system_prompt": "Old prompt",
        "is_preset": False
    })
    friend_id = create_res.json()["id"]

    # Update
    update_data = {
        "name": "Updated Friend Name",
        "system_prompt": "New prompt"
    }
    response = client.put(f"{settings.API_STR}/friends/{friend_id}", json=update_data)
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == "Updated Friend Name"
    assert content["system_prompt"] == "New prompt"
    assert content["description"] == "Before update" # Should remain unchanged


def test_update_friend_voice_config(client: TestClient):
    """
    Test updating friend voice config.
    """
    create_res = client.post(f"{settings.API_STR}/friends/", json={
        "name": "Voice Config Friend",
        "description": "Voice config test",
        "system_prompt": "Voice test prompt",
        "is_preset": False
    })
    friend_id = create_res.json()["id"]

    enable_res = client.put(f"{settings.API_STR}/friends/{friend_id}", json={
        "enable_voice": True,
        "voice_id": "Cherry"
    })
    assert enable_res.status_code == 200
    enable_content = enable_res.json()
    assert enable_content["enable_voice"] is True
    assert enable_content["voice_id"] == "Cherry"

    disable_res = client.put(f"{settings.API_STR}/friends/{friend_id}", json={
        "enable_voice": False
    })
    assert disable_res.status_code == 200
    disable_content = disable_res.json()
    assert disable_content["enable_voice"] is False
    assert disable_content["voice_id"] is None

def test_delete_friend(client: TestClient):
    """
    Test deleting a friend.
    """
    # Create
    create_res = client.post(f"{settings.API_STR}/friends/", json={
        "name": "Delete Test Friend",
        "description": "To be deleted",
        "system_prompt": "Bye bye",
        "is_preset": False
    })
    friend_id = create_res.json()["id"]

    # Delete
    response = client.delete(f"{settings.API_STR}/friends/{friend_id}")
    assert response.status_code == 200
    
    # Verify it's gone (or at least not retrievable via get)
    get_res = client.get(f"{settings.API_STR}/friends/{friend_id}")
    assert get_res.status_code == 404
