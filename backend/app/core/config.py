from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "Anilla"

    # Database
    DATABASE_URL: str = "postgresql://anilla:anilla@localhost:5432/anilla"

    # JWT / Auth
    SECRET_KEY: str = "CHANGE-ME-in-production-use-openssl-rand-hex-32"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Session
    SESSION_TIMEOUT_MINUTES: int = 15

    # AES-256 encryption key for PHI fields (base64-encoded 32-byte key)
    ENCRYPTION_KEY: str = "lAO2oizmHDDzVCFW__ketdDkaVkKRocUmfk0lLCOjCw="

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
