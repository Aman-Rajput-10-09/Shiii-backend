import os
from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "Shiii AI - Diplomatic Couple Emissary"
    API_V1_STR: str = "/api/v1"
    
    # Database (supports local, Supabase, Neon, and Vercel Postgres)
    DATABASE_URL: str = "postgresql+asyncpg://shiii_user:shiii_password@localhost:5432/shiii_db"

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def assemble_db_connection(cls, v: Optional[str]) -> str:
        if not v:
            v = os.getenv("POSTGRES_URL") or os.getenv("DATABASE_URL") or "postgresql+asyncpg://shiii_user:shiii_password@localhost:5432/shiii_db"
        if isinstance(v, str):
            if v.startswith("postgres://"):
                v = v.replace("postgres://", "postgresql+asyncpg://", 1)
            elif v.startswith("postgresql://") and not v.startswith("postgresql+asyncpg://"):
                v = v.replace("postgresql://", "postgresql+asyncpg://", 1)
            
            # Clean up asyncpg-incompatible query parameters (sslmode, channel_binding)
            if "?" in v:
                import urllib.parse
                parsed = urllib.parse.urlparse(v)
                query_params = urllib.parse.parse_qs(parsed.query)
                query_params.pop("sslmode", None)
                query_params.pop("channel_binding", None)
                new_query = urllib.parse.urlencode(query_params, doseq=True)
                v = urllib.parse.urlunparse(parsed._replace(query=new_query))
        return v
    
    # JWT Auth
    SECRET_KEY: str = "shiii_super_secret_cute_diplomat_key_change_in_production_2026"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 30  # 30 days
    
    # LLM (Gemini)
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-2.0-flash"
    
    # Voice (Edge-TTS)
    TTS_VOICE: str = "en-US-AnaNeural"
    TTS_RATE: str = "+10%"
    TTS_PITCH: str = "+35Hz"
    AUDIO_BASE_URL: str = "http://localhost:8000/static/audio"
    
    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
