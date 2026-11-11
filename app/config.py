import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./switch.db")
    pan_hash_key: str = os.getenv("PAN_HASH_KEY", "dev-only-key")
    enable_admin: bool = os.getenv("ENABLE_ADMIN", "true").lower() == "true"


settings = Settings()
