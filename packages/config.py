"""Minimal configuration for Gaokao Evidence Skill.

No external API dependencies — all analysis done by Claude Code itself.
"""

from __future__ import annotations

from pathlib import Path
from functools import lru_cache


class Settings:
    """Skill settings — path configuration only."""

    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.reports_dir = self.project_root / "reports"
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def claims_path(self, school: str, major: str) -> Path:
        return self.reports_dir / f"claims_{school}_{major}.json"

    def analysis_path(self, school: str, major: str) -> Path:
        return self.reports_dir / f"analysis_{school}_{major}.json"

    def report_path(self, school: str, major: str) -> Path:
        return self.reports_dir / f"{school}_{major}_报告.md"


@lru_cache
def get_settings() -> Settings:
    return Settings()
