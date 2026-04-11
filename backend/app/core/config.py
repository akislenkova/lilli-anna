from typing import Literal

from pydantic import ValidationInfo, field_validator, model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "Anilla"

    # development = auto-create tables + demo seed; staging/production = migrations only (Railway, etc.)
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"

    # When False (default), POST /auth/register only creates patient accounts. Set True for local dev
    # if you need self-serve test provider accounts — never enable on Railway production.
    ALLOW_STAFF_SELF_REGISTRATION: bool = False

    # Database
    DATABASE_URL: str = "postgresql://anilla:anilla@localhost:5432/anilla"

    # JWT / Auth — must be set via .env in all environments
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Session
    SESSION_TIMEOUT_MINUTES: int = 15

    @field_validator("SECRET_KEY")
    @classmethod
    def reject_placeholder_secret_in_production(cls, v: str, info: ValidationInfo) -> str:
        env = (info.data or {}).get("ENVIRONMENT", "development")
        if env == "production" and len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters in production")
        if env == "production" and v in ("change-me-in-production", "replace-me-with-openssl-rand-hex-32-output"):
            raise ValueError("SECRET_KEY must be set to a strong random value in production")
        return v

    # AES-256 encryption key for PHI fields (base64-encoded 32-byte key)
    # Generate with: python -c "import secrets, base64; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
    ENCRYPTION_KEY: str

    # CORS — add your production domain here or set via env var
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "https://anillahq.com",
        "https://www.anillahq.com",
        "https://anilla.vercel.app",
        "https://akislenkova-lilli-anna.vercel.app",
    ]
    FRONTEND_URL: str = "https://anillahq.com"

    @model_validator(mode="after")
    def include_frontend_url_in_cors(self):
        """Avoid browser CORS failures when FRONTEND_URL is set but omitted from CORS_ORIGINS (common on Vercel)."""
        u = self.FRONTEND_URL.rstrip("/")
        if not u:
            return self
        normalized = {o.rstrip("/") for o in self.CORS_ORIGINS}
        if u not in normalized:
            return self.model_copy(update={"CORS_ORIGINS": [*self.CORS_ORIGINS, self.FRONTEND_URL]})
        return self

    # Legacy EHR stub
    EHR_BASE_URL: str = "http://localhost:8081/ehr"
    EHR_API_KEY: str = ""

    # Epic FHIR / MyChart
    EPIC_FHIR_BASE_URL: str = "https://fhir.epic.com/interconnect-fhir-oauth"
    EPIC_CLIENT_ID: str = ""
    # Only needed for confidential clients; leave empty for public-client PKCE flow
    EPIC_CLIENT_SECRET: str = ""
    EPIC_MYCHART_BASE_URL: str = "https://mychart.epic.com/MyChart"

    # Voice transcription stub
    TRANSCRIPTION_SERVICE_URL: str = "http://localhost:8082/transcribe"

    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
    }


settings = Settings()
