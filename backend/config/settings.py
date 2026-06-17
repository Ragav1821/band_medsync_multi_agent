from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    app_name: str = "MedSync AI"
    version: str = "1.0.0"
    debug: bool = True

    # Database
    postgres_url: str = "postgresql+asyncpg://medsync:medsync123@localhost:5432/medsync_db"
    mongodb_url: str = "mongodb://localhost:27017"
    mongodb_db: str = "medsync_db"
    redis_url: str = "redis://localhost:6379"

    # JWT
    jwt_secret: str = "medsync-super-secret-jwt-key-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 8

    # Agent Settings
    agent_timeout_seconds: int = 45
    max_concurrent_agents: int = 10

    # Simulation
    simulation_mode: bool = True

    # Gemini AI
    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-2.5-flash"
    gemini_timeout: int = 30

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
