from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# chunking (usados por src/ingesta/chunkeo.py)
CHUNK_SIZE = 800
CHUNK_OVERLAP = 0

# embeddings: cambiar el modelo obliga a reindexar todos los documentos
MODELO_EMBEDDING = "openai/text-embedding-3-large"
DIMENSION_EMBEDDING = 3072

# recuperación y respuesta
K = 5
MODELO_LLM = "anthropic/claude-sonnet-5"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    database_url: str = "postgresql+psycopg://qa:qa@localhost:5432/qa_acreditacion"
    storage_dir: Path = Path("data/pdfs")
    max_pdf_mb: int = 50

    qdrant_url: str | None = None
    qdrant_api_key: str | None = None
    qdrant_path: str | None = "data/qdrant"
    qdrant_collection: str = "acreditacion_chunks"

    openrouter_api_key: str | None = None
    llm_model: str = MODELO_LLM
    embedding_model: str = MODELO_EMBEDDING
    embedding_dimension: int = Field(default=DIMENSION_EMBEDDING, gt=0)
    embedding_batch_size: int = Field(default=64, gt=0)
    top_k: int = Field(default=K, gt=0)

    stale_processing_minutes: int = 30


@lru_cache
def get_settings() -> Settings:
    return Settings()
