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

    # JWT — P0-2: must be overridden via JWT_SECRET env var in production
    jwt_secret: str = "medsync-super-secret-jwt-key-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 8

    # Agent Settings
    agent_timeout_seconds: int = 45
    max_concurrent_agents: int = 10

    # Simulation
    simulation_mode: bool = True

    # Gemini AI — key sourced from GEMINI_API_KEY env var, no default
    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-2.5-flash"
    gemini_timeout: int = 30

    # ─── Band of Agents — P0-1: NO hardcoded defaults; all keys come from .env ──
    # If a key is missing the Band service logs a warning and skips that call.
    band_api_base: str = "https://app.band.ai/api/v1"

    # Incident Commander
    band_commander_api_key: str = ""
    band_commander_agent_id: str = ""
    band_commander_handle: str = ""

    # Capacity Agent
    band_capacity_api_key: str = ""
    band_capacity_agent_id: str = ""
    band_capacity_handle: str = ""

    # Staffing Agent
    band_staffing_api_key: str = ""
    band_staffing_agent_id: str = ""
    band_staffing_handle: str = ""

    # Resource Agent
    band_resource_api_key: str = ""
    band_resource_agent_id: str = ""
    band_resource_handle: str = ""

    # Compliance Agent
    band_compliance_api_key: str = ""
    band_compliance_agent_id: str = ""
    band_compliance_handle: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
