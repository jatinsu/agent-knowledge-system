from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    gemini_api_key: str = "test_api_key"
    gemini_model: str = "gemini-2.0-flash"

    database_url: str = "sqlite:///./knowledge_system.db"

    github_token: str = ""
    jira_url: str = ""
    jira_email: str = ""
    jira_api_token: str = ""

    max_graph_hops: int = 3
    max_context_lines: int = 700
    rate_limit_requests_per_minute: int = 60


_settings: Optional[Settings] = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


settings = get_settings()
