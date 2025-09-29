from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    mongodb_uri: str = Field(default="mongodb://localhost:27017", alias="MONGODB_URI")
    mongodb_db: str = Field(default="logistics_db", alias="MONGODB_DB")
    port: int = Field(default=8000, alias="PORT")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
_client: Optional[AsyncIOMotorClient] = None
_db: Optional[AsyncIOMotorDatabase] = None

async def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.mongodb_uri)
    return _client

async def get_db() -> AsyncIOMotorDatabase:
    global _db
    if _db is None:
        client = await get_client()
        _db = client[settings.mongodb_db]
    return _db

async def close_db():
    global _client
    if _client is not None:
        _client.close()
        _client = None

def get_app_port() -> int:
    return settings.port
