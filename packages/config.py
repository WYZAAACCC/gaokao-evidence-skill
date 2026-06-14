"""Minimal configuration for Gaokao Evidence Skill.

Reads DeepSeek API key from apikey.txt, falls back to environment variables.
No heavy dependencies required (no pydantic-settings).
"""

from __future__ import annotations

import os
from pathlib import Path
from functools import lru_cache


class Settings:
    """Skill settings — reads from apikey.txt and environment."""

    def __init__(self):
        # Find project root (where apikey.txt lives)
        self.project_root = Path(__file__).parent.parent

        # API key: apikey.txt first, then env var
        apikey_path = self.project_root / "apikey.txt"
        if apikey_path.exists():
            self.deepseek_api_key = apikey_path.read_text().strip()
        else:
            self.deepseek_api_key = os.getenv("DEEPSEEK_API_KEY", "sk-placeholder")

        self.deepseek_base_url = os.getenv(
            "DEEPSEEK_BASE_URL", "https://api.deepseek.com"
        )
        self.llm_model = os.getenv("LLM_MODEL", "deepseek-chat")
        self.app_env = os.getenv("APP_ENV", "development")
        self.debug = os.getenv("DEBUG", "true").lower() == "true"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
