from functools import lru_cache
from pathlib import Path


_PROMPT_DIR = Path(__file__).resolve().parent


@lru_cache(maxsize=None)
def load_prompt(name: str) -> str:
    prompt_path = _PROMPT_DIR / name
    return prompt_path.read_text(encoding="utf-8")
