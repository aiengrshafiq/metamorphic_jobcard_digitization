from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    AZURE_STORAGE_CONNECTION_STRING: str
    OPENAI_API_KEY:str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60  # Default to 30 minutes if not set

    class Config:
        env_file = ".env"

settings = Settings()