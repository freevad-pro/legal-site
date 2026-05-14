from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    log_level: str = "INFO"
    corpus_path: Path = Path("docs/laws")
    playwright_timeout_seconds: int = 60
    user_agent: str = "LegalSiteScanner/0.1 (+https://github.com/freevad-pro/legal-site)"

    database_path: Path = Path("data/db.sqlite")
    basic_auth_realm: str = "Legal_site"
    scan_timeout_seconds: int = 300
    scan_state_ttl_seconds: int = 3600


settings = Settings()
