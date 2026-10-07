"""Helper functions: loading files, logging, JSON parsing, saving output."""

import json
import logging
import re
from pathlib import Path
from typing import Any

import yaml


def setup_logging(level: str = "INFO") -> None:
    """Configure console logging."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    # Silence noisy third-party libraries
    logging.getLogger("google_genai").setLevel(logging.ERROR)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def load_yaml(path: str) -> dict:
    """Load a YAML file and return it as a dictionary."""
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    with file_path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_config(path: str = "config/config.yaml") -> dict:
    """Load the project configuration."""
    return load_yaml(path)


def load_prompts(path: str = "prompts/prompts.yaml") -> dict:
    """Load the prompt templates."""
    return load_yaml(path)


def read_text(path: str) -> str:
    """Read a text file (the meeting transcript)."""
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Transcript not found: {file_path}")
    text = file_path.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(f"Transcript file is empty: {file_path}")
    return text


def render_prompt(template: str, **values: Any) -> str:
    """Fill {placeholders} in a prompt template.

    Uses simple replacement instead of str.format so the JSON braces
    inside the prompts do not cause errors.
    """
    for key, value in values.items():
        template = template.replace("{" + key + "}", str(value))
    return template.strip()


def parse_json(text: str) -> Any:
    """Parse JSON from a model reply, tolerating ```json fences and extra text."""
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start != -1 and end > start:
            return json.loads(cleaned[start : end + 1])
        raise


def save_json(data: Any, path: str) -> None:
    """Save data as pretty-printed JSON."""
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def save_text(text: str, path: str) -> None:
    """Save plain text to a file."""
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(text, encoding="utf-8")
