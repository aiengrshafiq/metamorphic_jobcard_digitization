from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    AZURE_STORAGE_CONNECTION_STRING: str
    OPENAI_API_KEY:str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # Default to 30 minutes if not set
    SLACK_DESIGN_WEBHOOK_URL: str
    SLACK_WEBHOOK_URL: Optional[str] = None
    BASE_URL: str = "http://127.0.0.1:8000/"  # Default base URL

    class Config:
        env_file = ".env"

settings = Settings()