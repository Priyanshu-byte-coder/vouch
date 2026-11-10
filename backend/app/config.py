"""Runtime settings, read from the repo-root .env (never committed)."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", env_file_encoding="utf-8", extra="ignore")

    # Scholarly APIs
    crossref_mailto: str = ""
    openalex_api_key: str = ""
    openalex_api_key_2: str = ""
    openalex_api_key_3: str = ""
    s2_api_key: str = ""
    s2_min_interval: float = 1.1

    # LLM (any OpenAI-compatible endpoint)
    llm_base_url: str = "https://api.vultrinference.com/v1"
    llm_api_key: str = ""
    llm_model_parse: str = "deepseek-v4.1-flash-1017"
    llm_model_judge: str = "deepseek-v4.1-flash-1017"
    llm_timeout: float = 90.0
    # USD per million tokens, used for cost reporting
    llm_price_in_per_m: float = 0.55
    llm_price_out_per_m: float = 2.75

    # Services
    grobid_url: str = "http://localhost:8070"
    cache_path: str = "./cache.sqlite"

    @property
    def openalex_keys(self) -> list[str]:
        """Keys in rotation order; empty slots skipped."""
        return [k for k in (self.openalex_api_key, self.openalex_api_key_2, self.openalex_api_key_3) if k]

    @property
    def cache_file(self) -> Path:
        p = Path(self.cache_path)
        return p if p.is_absolute() else ROOT / p

    @property
    def user_agent(self) -> str:
        contact = f"; mailto:{self.crossref_mailto}" if self.crossref_mailto else ""
        return f"Vouch/0.1 (research-integrity screener; https://github.com/Priyanshu-byte-coder/vouch{contact})"


@lru_cache
def get_settings() -> Settings:
    return Settings()
