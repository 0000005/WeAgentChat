import os
import re
import logging
from typing import List
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

    def sync_voice_timbres(self, html_path: str):
        """解析 tts-sample.html 并将音色数据同步到数据库（upsert）。"""
        if not os.path.exists(html_path):
            logger.warning(f"Voice list file not found: {html_path}")
            return

        try:
            with open(html_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Split by <tr>
            rows = re.findall(r'<tr.*?>(.*?)</tr>', content, re.DOTALL)

            count = 0
            for row in rows:
                # Skip header row (contains "voice参数" header)
                if 'voice' in row and '参数' in row and '详情' in row:
                    continue

                # Extract voice_id from <code class="code">...</code>
                voice_id_match = re.search(r'<code[^>]*class="code"[^>]*>(.*?)</code>', row, re.DOTALL)
                if not voice_id_match:
                    continue
                voice_id = voice_id_match.group(1).strip()

                # Extract name (音色名)
                name_match = re.search(r'音色名</b>：(.*?)</p>', row, re.DOTALL)
                name = name_match.group(1).strip() if name_match else voice_id

                # Extract description (描述)
                desc_match = re.search(r'描述</b>：(.*?)(?:<audio|</p>)', row, re.DOTALL)
                description = desc_match.group(1).strip() if desc_match else ""
                # Clean up HTML tags like <span class="help-letter-space"></span>
                description = re.sub(r'<[^>]+>', '', description)

                # Infer gender from description
                gender = "female" if "女性" in description else "male" if "男性" in description else "unknown"

                # Extract preview_url: prefer src over data-src for reliability
                url_match = re.search(r'<audio[^>]*\bsrc="(https://[^"]+)"', row, re.DOTALL)
                if not url_match:
                    url_match = re.search(r'<audio[^>]*data-src="(https://[^"]+)"', row, re.DOTALL)
                preview_url = url_match.group(1).strip() if url_match else ""

                # Extract supported models from the 4th <td>
                tds = re.findall(r'<td.*?>(.*?)</td>', row, re.DOTALL)
                supported_models = ""
                if len(tds) >= 4:
                    model_matches = re.findall(r'qwen[\w-]+', tds[3])
                    supported_models = ",".join(sorted(set(model_matches)))

                # Upsert: update existing or create new
                voice = self.db.query(VoiceTimbre).filter(VoiceTimbre.voice_id == voice_id).first()
                if not voice:
                    voice = VoiceTimbre(
                        voice_id=voice_id,
                        name=name,
                        description=description,
                        gender=gender,
                        preview_url=preview_url,
                        supported_models=supported_models,
                        category="Standard"
                    )
                    self.db.add(voice)
                else:
                    voice.name = name
                    voice.description = description
                    voice.gender = gender
                    voice.preview_url = preview_url
                    voice.supported_models = supported_models

                count += 1

            self.db.commit()
            logger.info(f"Successfully synced {count} voice timbres from {html_path}")
        except Exception as e:
            logger.error(f"Error syncing voice timbres: {e}")
            self.db.rollback()

    @staticmethod
    def initialize_voices():
        """Initialize voices from local HTML file on startup.

        TODO: For Electron packaging, consider converting to a SQL seed file
        under server/app/db/ (like init_persona_templates.sql) so it does not
        depend on dev-docs/ being present at runtime.
        """
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        html_path = os.path.join(base_dir, "dev-docs", "temp", "tts-sample.html")

        db = SessionLocal()
        try:
            service = VoiceService(db)
            service.sync_voice_timbres(html_path)
        finally:
            db.close()


def get_voice_service(db: Session) -> VoiceService:
    return VoiceService(db)
