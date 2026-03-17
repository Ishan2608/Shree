from pydantic_settings import BaseSettings

class Settings(BaseSettings):
  """
  Loads all configuration from environment variables or the .env file.

  Pydantic-settings automatically reads the .env file at startup.
  You never need to call dotenv.load() anywhere else in the project.

  Usage in any file:
    from config import settings
    print(settings.GEMINI_API_KEY)
  """
  GEMINI_API_KEY: str
  TAVILY_API_KEY: str
  NEWS_API_KEY: str
  UPLOAD_DIR: str = "uploads"
  SESSION_TTL_SECONDS: int = 3600

  class Config:
    env_file = ".env"
    env_file_encoding = "utf-8"


# Instantiate settings as a module-level singleton.
# Every other file imports this 'settings' object — never re-instantiate it.
settings = Settings()
