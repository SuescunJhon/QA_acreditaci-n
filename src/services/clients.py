from langchain_openai import OpenAIEmbeddings
from langchain_openrouter.chat_models import ChatOpenRouter

from src.config.settings import Settings

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def _require_api_key(settings: Settings) -> str:
    if not settings.openrouter_api_key:
        raise ValueError("Falta la variable OPENROUTER_API_KEY.")
    return settings.openrouter_api_key


def get_llm(settings: Settings) -> ChatOpenRouter:
    return ChatOpenRouter(model=settings.llm_model, api_key=_require_api_key(settings))


def get_embeddings(settings: Settings) -> OpenAIEmbeddings:
    return OpenAIEmbeddings(
        model=settings.embedding_model,
        base_url=OPENROUTER_BASE_URL,
        api_key=_require_api_key(settings),
        check_embedding_ctx_length=False,
    )
