from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FPL_", env_file=".env", extra="ignore")

    app_name: str = "Live FPL Strategy Engine"
    app_version: str = "1.0.0"
    environment: str = Field(default="dev", pattern="^(dev|staging|prod)$")

    host: str = "0.0.0.0"
    port: int = 8000
    tick_seconds: float = Field(default=1.0, gt=0.0)
    simulation_samples: int = Field(default=10000, ge=1000)

    ws_push_seconds: float = Field(default=1.0, gt=0.0)
    api_key: str | None = None

    data_source: str = Field(default="mock", pattern="^(mock|fpl)$")
    fpl_base_url: str = "https://fantasy.premierleague.com/api"
    fpl_current_event: int | None = None
    fpl_entry_ids: str = ""
    fpl_request_timeout_seconds: float = Field(default=10.0, gt=0.0)
    fpl_user_agent: str = "fpl-strategy-engine/1.0"

    snapshot_limit: int = Field(default=1000, ge=100)
    event_limit: int = Field(default=10000, ge=100)
    sqlite_path: str = "./data/fpl_engine.db"

    metrics_enabled: bool = True
    random_seed: int = 2026

    @property
    def parsed_entry_ids(self) -> list[int]:
        raw = self.fpl_entry_ids.strip()
        if not raw:
            return []
        return [int(item.strip()) for item in raw.split(",") if item.strip()]


def get_settings() -> Settings:
    return Settings()
