import os
import tomli
from dotenv import load_dotenv
from pathlib import Path
from pydantic import BaseModel


class DatabaseSettings(BaseModel):
    host: str
    port: int
    name: str
    user: str
    password: str

    def url(self) -> str:
        host = os.getenv("DB_HOST", self.host)
        pw = os.getenv("POSTGRES_PASSWORD", self.password)
        return f"postgresql+psycopg://{self.user}:{pw}@{host}:{self.port}/{self.name}"


class RedisSettings(BaseModel):
    host: str
    port: int
    db: int


class LLMSettings(BaseModel):
    provider: str
    base_url: str
    api_key_env_var: str
    tool_model: str
    synthesis_model: str
    tool_temperature: float
    synthesis_temperature: float

    @property
    def api_key(self) -> str | None:
        return os.getenv(self.api_key_env_var) or None


class EmbeddingSettings(BaseModel):
    model: str
    dim: int


class RetrievalSettings(BaseModel):
    top_k: int
    hnsw_m: int
    hnsw_ef_construction: int


class AgentSettings(BaseModel):
    max_tool_iterations: int


class CacheSettings(BaseModel):
    product_ttl_seconds: int
    compatibility_ttl_seconds: int
    retrieval_ttl_seconds: int


class ScopeSettings(BaseModel):
    appliance_keywords: list[str]
    out_of_scope_keywords: list[str]


class Settings(BaseModel):
    database: DatabaseSettings
    redis: RedisSettings
    llm: LLMSettings
    embeddings: EmbeddingSettings
    retrieval: RetrievalSettings
    agent: AgentSettings
    cache: CacheSettings
    scope: ScopeSettings


def load_settings(path: str | Path | None = None) -> Settings:
    if path is None:
        path = Path(__file__).resolve().parents[2] / "config.toml"
    with open(path, "rb") as f:
        raw = tomli.load(f)
    return Settings(**raw)
