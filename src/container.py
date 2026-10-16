from dataclasses import dataclass

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from src.config.settings import Settings
from src.db.session import create_db_engine, create_session_factory
from src.services.auth import AuthService
from src.services.chat import ChatService
from src.services.clients import get_embeddings, get_llm
from src.services.documents import DocumentService
from src.services.rag import RagService
from src.storage.files import LocalFileStorage
from src.vectorstore.qdrant import QdrantRepository, create_qdrant_client


@dataclass
class Container:
    settings: Settings
    engine: Engine
    session_factory: sessionmaker[Session]
    auth: AuthService
    documents: DocumentService
    chat: ChatService


def build_container(settings: Settings) -> Container:
    engine = create_db_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    repository = QdrantRepository(
        create_qdrant_client(settings), settings.qdrant_collection, settings.embedding_dimension
    )
    embeddings = get_embeddings(settings)
    storage = LocalFileStorage(settings.storage_dir)
    documents = DocumentService(session_factory, storage, repository, embeddings, settings)
    rag = RagService(embeddings, repository, get_llm(settings), settings.top_k)
    return Container(
        settings=settings,
        engine=engine,
        session_factory=session_factory,
        auth=AuthService(session_factory),
        documents=documents,
        chat=ChatService(session_factory, rag),
    )
