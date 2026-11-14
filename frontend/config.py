import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    api_url: str

    @classmethod
    def from_environment(cls) -> "Settings":
        return cls(
            api_url=os.getenv(
                "BIBLIOTECA_API_URL", "http://127.0.0.1:8000"
            ).rstrip("/")
        )
