"""Minimal configuration for Gaokao Evidence Skill.

Reads DeepSeek API key from apikey.txt, falls back to environment variables.
No heavy dependencies required (no pydantic-settings).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from functools import lru_cache

_PLACEHOLDER_PATTERNS = [
    "sk-your-", "sk-placeholder", "your-api-key", "your-deepseek",
]


class Settings:
    """Skill settings — reads from apikey.txt and environment."""

    def __init__(self):
        self.project_root = Path(__file__).parent.parent

        # API key: apikey.txt first, then env var
        apikey_path = self.project_root / "apikey.txt"
        if apikey_path.exists():
            self.deepseek_api_key = apikey_path.read_text().strip()
        else:
            self.deepseek_api_key = os.getenv("DEEPSEEK_API_KEY", "sk-placeholder")

        self._validate_api_key()

        self.deepseek_base_url = os.getenv(
            "DEEPSEEK_BASE_URL", "https://api.deepseek.com"
        )
        self.llm_model = os.getenv("LLM_MODEL", "deepseek-chat")
        self.app_env = os.getenv("APP_ENV", "development")
        self.debug = os.getenv("DEBUG", "true").lower() == "true"

    def _validate_api_key(self) -> None:
        for pattern in _PLACEHOLDER_PATTERNS:
            if pattern in self.deepseek_api_key.lower():
                print(
                    f"\n{'=' * 60}\n"
                    f"  WARNING: apikey.txt 包含占位符密钥 '{self.deepseek_api_key[:20]}...'\n"
                    f"  请替换为真实 DeepSeek API Key: https://platform.deepseek.com/api_keys\n"
                    f"{'=' * 60}\n",
                    file=sys.stderr,
                )
                return

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
