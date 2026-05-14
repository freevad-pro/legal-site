from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    log_level: str = "INFO"
    corpus_path: Path = Path("docs/laws")
    playwright_timeout_seconds: int = 60
    user_agent: str = "LegalSiteScanner/0.1 (+https://github.com/freevad-pro/legal-site)"

    database_path: Path = Path("data/db.sqlite")
    scan_timeout_seconds: int = 300
    scan_state_ttl_seconds: int = 3600

    # Session cookie. `session_cookie_secure=False` — безопасный default для
    # локального dev по http://127.0.0.1; в проде поднимаем через ENV.
    session_cookie_name: str = "legal_site_session"
    session_ttl_days: int = 30
    session_cookie_secure: bool = False

    # CORS-origins для фронта в режиме разработки (Next.js на :3000).
    # В production оставляем пустым — фронт лежит на одном origin с API,
    # CORSMiddleware не подключается. Связь с `session_cookie_secure` сознательно
    # не делаем: «secure cookie» и «нужен CORS» — независимые решения.
    cors_dev_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]


settings = Settings()
