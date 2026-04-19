"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Settings loaded from .env file and environment variables.

    All sensitive configuration (database credentials, API tokens) should be
    set via environment variables or .env file - never hardcoded.
    """

    # Database
    database_url: str = "mysql+aiomysql://root:password@localhost:3306/stock_logic"

    # Tushare Pro API
    tushare_token: str = ""
    tushare_rate_limit: int = 80  # calls per minute (free tier limit)
    tushare_daily_limit: int = 500  # calls per day (free tier limit)

    # Scheduler
    scheduler_timezone: str = "Asia/Shanghai"

    # Logging
    log_level: str = "INFO"

    # Request timeouts
    request_timeout: int = 30

    # LLM API keys (for Phase 3+)
    openai_api_key: str = ""
    anthropic_api_key: str = ""

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"


settings = Settings()
