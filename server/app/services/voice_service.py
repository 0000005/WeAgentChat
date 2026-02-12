import os
import re
import json
import logging
from pathlib import Path
from typing import Any, Dict, List
from sqlalchemy.orm import Session
from app.models.voice import VoiceTimbre
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)


class VoiceService:
    def __init__(self, db: Session):
        self.db = db

    def get_all_timbres(self) -> List[VoiceTimbre]:
        return self.db.query(VoiceTimbre).all()

    def get_timbre_by_voice_id(self, voice_id: str) -> VoiceTimbre | None:
        return self.db.query(VoiceTimbre).filter(VoiceTimbre.voice_id == voice_id).first()

    def _upsert_voice_timbres(self, timbres: List[Dict[str, Any]], source: str) -> int:
        count = 0
        for item in timbres:
            voice_id = str(item.get("voice_id") or "").strip()
            if not voice_id:
                continue

            name = str(item.get("name") or voice_id).strip() or voice_id
            description = str(item.get("description") or "").strip()
            gender = str(item.get("gender") or "").strip() or "unknown"
            preview_url = str(item.get("preview_url") or "").strip()
            category = str(item.get("category") or "Standard").strip() or "Standard"

            supported_models_raw = item.get("supported_models")
            if isinstance(supported_models_raw, list):
                supported_models = ",".join(
                    sorted(
                        {
                            str(model).strip()
                            for model in supported_models_raw
                            if str(model).strip()
                        }
                    )
                )
            else:
                supported_models = str(supported_models_raw or "").strip()

            voice = self.db.query(VoiceTimbre).filter(VoiceTimbre.voice_id == voice_id).first()
            if not voice:
                voice = VoiceTimbre(
                    voice_id=voice_id,
                    name=name,
                    description=description,
                    gender=gender,
                    preview_url=preview_url,
                    supported_models=supported_models,
                    category=category,
                )
                self.db.add(voice)
            else:
                voice.name = name
                voice.description = description
                voice.gender = gender
                voice.preview_url = preview_url
                voice.supported_models = supported_models
                voice.category = category
            count += 1

        self.db.commit()
        logger.info("Successfully synced %s voice timbres from %s", count, source)
        return count

    def sync_voice_timbres(self, html_path: str) -> int:
        """解析 tts-sample.html 并将音色数据同步到数据库（upsert）。"""
        if not os.path.exists(html_path):
            logger.warning("Voice list file not found: %s", html_path)
            return 0

        try:
            with open(html_path, "r", encoding="utf-8") as f:
                content = f.read()

            rows = re.findall(r"<tr.*?>(.*?)</tr>", content, re.DOTALL)
            timbres: List[Dict[str, Any]] = []

            for row in rows:
                if "voice" in row and "参数" in row and "详情" in row:
                    continue

                voice_id_match = re.search(
                    r'<code[^>]*class="code"[^>]*>(.*?)</code>',
                    row,
                    re.DOTALL,
                )
                if not voice_id_match:
                    continue
                voice_id = voice_id_match.group(1).strip()

                name_match = re.search(r"音色名</b>：(.*?)</p>", row, re.DOTALL)
                name = name_match.group(1).strip() if name_match else voice_id

                desc_match = re.search(r"描述</b>：(.*?)(?:<audio|</p>)", row, re.DOTALL)
                description = desc_match.group(1).strip() if desc_match else ""
                description = re.sub(r"<[^>]+>", "", description)

                gender = "female" if "女性" in description else "male" if "男性" in description else "unknown"

                url_match = re.search(r'<audio[^>]*\bsrc="(https://[^"]+)"', row, re.DOTALL)
                if not url_match:
                    url_match = re.search(r'<audio[^>]*data-src="(https://[^"]+)"', row, re.DOTALL)
                preview_url = url_match.group(1).strip() if url_match else ""

                tds = re.findall(r"<td.*?>(.*?)</td>", row, re.DOTALL)
                supported_models: List[str] = []
                if len(tds) >= 4:
                    supported_models = sorted(set(re.findall(r"qwen[\w-]+", tds[3])))

                timbres.append(
                    {
                        "voice_id": voice_id,
                        "name": name,
                        "description": description,
                        "gender": gender,
                        "preview_url": preview_url,
                        "supported_models": supported_models,
                        "category": "Standard",
                    }
                )

            return self._upsert_voice_timbres(timbres, html_path)
        except Exception as e:
            logger.error("Error syncing voice timbres from html: %s", e)
            self.db.rollback()
            return 0

    def sync_voice_timbres_from_seed(self, seed_path: str) -> int:
        """从内置 JSON 种子同步音色数据（适用于打包环境）。"""
        if not os.path.exists(seed_path):
            logger.warning("Voice seed file not found: %s", seed_path)
            return 0

        try:
            with open(seed_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            timbres = payload if isinstance(payload, list) else []
            return self._upsert_voice_timbres(timbres, seed_path)
        except Exception as e:
            logger.error("Error syncing voice timbres from seed: %s", e)
            self.db.rollback()
            return 0

    @staticmethod
    def initialize_voices():
        """Initialize voices from local HTML file on startup.
        """
        service_file = Path(__file__).resolve()
        app_dir = service_file.parent.parent
        server_dir = app_dir.parent
        project_root = server_dir.parent

        html_candidates = [
            project_root / "dev-docs" / "temp" / "tts-sample.html",
            server_dir / "dev-docs" / "temp" / "tts-sample.html",
        ]
        seed_candidates = [
            app_dir / "db" / "voice_timbres_seed.json",
        ]

        db = SessionLocal()
        try:
            service = VoiceService(db)
            for html_path in html_candidates:
                if html_path.exists() and service.sync_voice_timbres(str(html_path)) > 0:
                    return

            for seed_path in seed_candidates:
                if seed_path.exists() and service.sync_voice_timbres_from_seed(str(seed_path)) > 0:
                    return

            logger.warning(
                "Voice timbre initialization skipped: no valid source found. html_candidates=%s seed_candidates=%s",
                [str(p) for p in html_candidates],
                [str(p) for p in seed_candidates],
            )
        finally:
            db.close()


def get_voice_service(db: Session) -> VoiceService:
    return VoiceService(db)
