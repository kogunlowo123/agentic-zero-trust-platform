from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    azure_openai_endpoint: str = ""  # Override via AZURE_OPENAI_ENDPOINT env var
    azure_openai_api_key: SecretStr = SecretStr("")  # Override via AZURE_OPENAI_API_KEY
    azure_openai_embedding_deployment: str = "text-embedding-3-large"
    database_url: SecretStr  # Required: set DATABASE_URL env var
    opensearch_url: str = "http://localhost:9200"
    embedding_model: str = "BAAI/bge-large-en-v1.5"
    embedding_batch_size: int = 32
    chunk_size: int = 512
    chunk_overlap: int = 64
    top_k_dense: int = 10
    top_k_sparse: int = 10
    rerank_top_k: int = 5
    cache_ttl_seconds: int = 3600
    environment: str = "development"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
