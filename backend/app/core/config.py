from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "Anilla"

    # Database
    DATABASE_URL: str = "postgresql://anilla:anilla@localhost:5432/anilla"

    # JWT / Auth — must be set via .env in all environments
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Session
    SESSION_TIMEOUT_MINUTES: int = 15

    # AES-256 encryption key for PHI fields (base64-encoded 32-byte key)
    # Generate with: python -c "import secrets, base64; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
    ENCRYPTION_KEY: str

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    # Epic MyChart EHR stub
    EHR_BASE_URL: str = "http://localhost:8081/ehr"
    EHR_API_KEY: str = ""

    # Voice transcription stub
    TRANSCRIPTION_SERVICE_URL: str = "http://localhost:8082/transcribe"

    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
    }


settings = Settings()
