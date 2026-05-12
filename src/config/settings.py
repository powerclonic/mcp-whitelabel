from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Application
    app_name: str = "mcp-governance-server"
    app_version: str = "0.1.0"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Qdrant
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "governance"
    qdrant_vector_size: int = 1024

    # Embedding service
    embedding_url: str = "http://localhost:8001/embed"
    embedding_model: str = "BAAI/bge-m3"

    # Chunking
    chunk_max_size: int = 512
    chunk_overlap: int = 64

    # Auth / OIDC
    oidc_issuer: str = "https://auth.example.com"
    oidc_audience: str = "mcp-governance"
    jwks_cache_ttl_seconds: int = 3600


settings = Settings()
