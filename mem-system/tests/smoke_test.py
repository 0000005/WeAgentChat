import httpx
import asyncio
import uuid

BASE_URL = "http://127.0.0.1:8019/api/v1"
TOKEN = "Bearer test-token"

async def test_api():
    async with httpx.AsyncClient(headers={"Authorization": TOKEN}, timeout=30.0) as client:
        # 1. Healthcheck
        print("Testing /healthcheck...")
        resp = await client.get(f"{BASE_URL}/healthcheck")
        print(f"Healthcheck: {resp.status_code}, {resp.json()}")
        assert resp.status_code == 200

        # 2. Create User
        desired_id = str(uuid.uuid4())
        print(f"Testing /users (Create User with id {desired_id})...")
        # UserData has 'id' field. Sending directly.
        resp = await client.post(f"{BASE_URL}/users", json={"id": desired_id})
        print(f"Create User: {resp.status_code}, {resp.json()}")
        assert resp.status_code == 200
        
        user_id = resp.json()['data']['id']
        print(f"Using user_id: {user_id}")

        # 3. Get User
        print(f"Testing /users/{user_id} (Get User)...")
        resp = await client.get(f"{BASE_URL}/users/{user_id}")
        print(f"Get User: {resp.status_code}, {resp.json()}")
        assert resp.status_code == 200

        # 4. Insert Blob (Chat)
        print(f"Testing /blobs/insert/{user_id}...")
        # Payload must match BlobData exactly.
        blob_payload = {
            "blob_type": "chat",
            "blob_data": {
                "messages": [
                    {"role": "user", "content": "昨天我买了一台新的电脑，配置很高，玩游戏很流畅。"},
                    {"role": "assistant", "content": "听起来很棒！你主要用它玩什么游戏呢？"}
                ]
            }
        }
        resp = await client.post(f"{BASE_URL}/blobs/insert/{user_id}", json=blob_payload)
        print(f"Insert Blob: {resp.status_code}, {resp.json()}")
        assert resp.status_code == 200

        # 5. Flush Buffer (Force processing)
        print(f"Testing /users/buffer/{user_id}/chat (Flush Buffer)...")
        resp = await client.post(f"{BASE_URL}/users/buffer/{user_id}/chat")
        print(f"Flush Buffer: {resp.status_code}, {resp.json()}")
        assert resp.status_code == 200

        # 6. Get User Context
        print(f"Testing /users/context/{user_id}...")
        resp = await client.get(f"{BASE_URL}/users/context/{user_id}")
        print(f"Get Context: {resp.status_code}, {resp.json()}")
        assert resp.status_code == 200

        # 7. Search Events (Vector Search)
        print(f"Testing /users/event/search/{user_id} (Vector Search)...")
        # User lowercase 'topk' as per api_layer/event.py
        resp = await client.get(f"{BASE_URL}/users/event/search/{user_id}", params={"query": "电脑", "topk": 5})
        print(f"Search Events: {resp.status_code}, {resp.json()}")
        assert resp.status_code == 200

        print("\nSmoke test passed successfully!")

if __name__ == "__main__":
    asyncio.run(test_api())
