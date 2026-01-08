from app.prompt.loader import load_prompt


def get_prompt(name: str) -> str:
    return load_prompt(name)
