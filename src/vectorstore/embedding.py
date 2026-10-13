from src.config.settings import MODELO_EMBEDDING
from services.clients import get_embedding

def embedding(texts):
    if not texts:
        return []
    return get_embedding().embed_documents(texts)
    