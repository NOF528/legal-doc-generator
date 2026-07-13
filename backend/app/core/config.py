from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # API
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "法律文档生成器"
    
    # CORS
    BACKEND_CORS_ORIGINS: list = ["http://localhost:3000"]
    
    # OpenAI
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_BASE_URL: Optional[str] = "https://api.moonshot.cn/v1"
    OPENAI_MODEL: str = "moonshot-v1-128k"
    
    # Upload paths
    TEMPLATE_DIR: str = "uploads/templates"
    GENERATED_DIR: str = "uploads/generated"
    KNOWLEDGE_BASE_DIR: str = "uploads/knowledge_base"
    
    # ChromaDB
    CHROMA_PERSIST_DIR: str = "./chroma_db"
    
    class Config:
        env_file = ".env"


settings = Settings()
