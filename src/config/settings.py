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
    # Base URL without path (e.g. http://localhost:8001).
    # /embed and /embed_sparse are derived from this automatically.
    embedding_base_url: str = "http://localhost:8001"
    embedding_model: str = "BAAI/bge-m3"

    @property
    def embedding_url(self) -> str:
        return f"{self.embedding_base_url}/embed"

    @property
    def embedding_sparse_url(self) -> str:
        return f"{self.embedding_base_url}/embed_sparse"

    # Sparse / hybrid search (BGE-M3 supports sparse embeddings natively)
    sparse_search_enabled: bool = True

    # Reranker service (cross-encoder, e.g. BAAI/bge-reranker-v2-m3)
    reranker_enabled: bool = False
    reranker_url: str = "http://localhost:8002/rerank"
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    rerank_candidate_k: int = 20  # candidates fetched from Qdrant
    rerank_top_n: int = 5         # final results returned to caller

    # Chunking
    chunk_max_size: int = 512
    chunk_overlap: int = 64

    # Auth / OIDC
    oidc_issuer: str = "https://auth.example.com"
    oidc_audience: str = "mcp-governance"
    jwks_cache_ttl_seconds: int = 3600


settings = Settings()
