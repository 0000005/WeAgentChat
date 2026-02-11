from unittest.mock import MagicMock, patch

from app.core.config import settings
from app.models.voice import VoiceTimbre


def _ensure_voice(db, voice_id: str = "Cherry") -> None:
    exists = db.query(VoiceTimbre).filter(VoiceTimbre.voice_id == voice_id).first()
    if exists:
        return
    db.add(
        VoiceTimbre(
            voice_id=voice_id,
            name="芊悦",
            description="测试音色",
            gender="female",
            preview_url="https://example.com/cherry.wav",
            supported_models="qwen3-tts-instruct-flash",
            category="Standard",
        )
    )
    db.commit()


def test_get_voice_timbres(client, db):
    _ensure_voice(db, "Cherry")
    response = client.get(f"{settings.API_STR}/voice/timbres")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert any(item["voice_id"] == "Cherry" for item in data)


def test_test_voice_config_success(client, db):
    _ensure_voice(db, "Cherry")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "output": {
            "audio": {
                "url": "https://example.com/test-audio.wav"
            }
        }
    }

    with patch("app.api.endpoints.voice.get_prompt", return_value="你好，我是测试语音。"), \
         patch("app.api.endpoints.voice.httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value.__enter__.return_value = mock_client

        response = client.post(
            f"{settings.API_STR}/voice/test",
            json={
                "api_key": "sk-test",
                "model": "qwen3-tts-instruct-flash",
                "voice_id": "Cherry",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["voice_id"] == "Cherry"
    assert payload["audio_url"] == "https://example.com/test-audio.wav"


def test_test_voice_config_requires_valid_voice(client, db):
    response = client.post(
        f"{settings.API_STR}/voice/test",
        json={
            "api_key": "sk-test",
            "model": "qwen3-tts-instruct-flash",
            "voice_id": "NotExistsVoice",
        },
    )
    assert response.status_code == 400
    assert "音色不存在" in response.json()["detail"]
