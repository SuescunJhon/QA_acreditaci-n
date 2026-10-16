import uuid
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload, sessionmaker

from src.db.models import Conversation, Document, Message, MessageCitation, utcnow
from src.db.session import session_scope
from src.services.rag import RagService

DEFAULT_TITLE = "Nueva conversación"
MAX_TITLE = 60


class ConversationNotFoundError(LookupError):
    pass


@dataclass(frozen=True)
class CitationView:
    document_id: uuid.UUID | None
    document_name: str
    page_start: int | None
    page_end: int | None
    chunk_type: str | None
    chunk_text: str
    score: float | None
    position: int

    @property
    def pages_label(self) -> str | None:
        if self.page_start is None:
            return None
        if self.page_end in (None, self.page_start):
            return str(self.page_start)
        return f"{self.page_start}-{self.page_end}"


@dataclass(frozen=True)
class MessageView:
    id: uuid.UUID
    role: str
    content: str
    created_at: datetime
    citations: list[CitationView] = field(default_factory=list)


@dataclass(frozen=True)
class ConversationView:
    id: uuid.UUID
    title: str
    updated_at: datetime


def _title_from(question: str) -> str:
    title = " ".join(question.split())
    return title if len(title) <= MAX_TITLE else title[: MAX_TITLE - 1] + "…"


def _message_view(message: Message) -> MessageView:
    return MessageView(
        id=message.id,
        role=message.role,
        content=message.content,
        created_at=message.created_at,
        citations=[
            CitationView(
                c.document_id, c.document_name, c.page_start, c.page_end,
                c.chunk_type, c.chunk_text, c.score, c.position,
            )
            for c in message.citations
        ],
    )


class ChatService:
    def __init__(self, session_factory: sessionmaker[Session], rag: RagService):
        self.session_factory = session_factory
        self.rag = rag

    def _owned(self, session: Session, user_id: uuid.UUID, conversation_id: uuid.UUID) -> Conversation:
        conv = session.scalar(
            select(Conversation).where(
                Conversation.id == conversation_id, Conversation.user_id == user_id
            )
        )
        if conv is None:
            raise ConversationNotFoundError(str(conversation_id))
        return conv

    def create_conversation(self, user_id: uuid.UUID, title: str = DEFAULT_TITLE) -> ConversationView:
        with session_scope(self.session_factory) as session:
            conv = Conversation(user_id=user_id, title=title)
            session.add(conv)
            session.flush()
            session.refresh(conv)
            return ConversationView(conv.id, conv.title, conv.updated_at)

    def list_conversations(self, user_id: uuid.UUID) -> list[ConversationView]:
        with session_scope(self.session_factory) as session:
            rows = session.scalars(
                select(Conversation)
                .where(Conversation.user_id == user_id)
                .order_by(Conversation.updated_at.desc())
            )
            return [ConversationView(c.id, c.title, c.updated_at) for c in rows]

    def get_messages(self, user_id: uuid.UUID, conversation_id: uuid.UUID) -> list[MessageView]:
        with session_scope(self.session_factory) as session:
            self._owned(session, user_id, conversation_id)
            rows = session.scalars(
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .options(selectinload(Message.citations))
                .order_by(Message.created_at)
            )
            return [_message_view(m) for m in rows]

    def delete_conversation(self, user_id: uuid.UUID, conversation_id: uuid.UUID) -> None:
        with session_scope(self.session_factory) as session:
            conv = self._owned(session, user_id, conversation_id)
            session.delete(conv)

    def ask(self, user_id: uuid.UUID, conversation_id: uuid.UUID, question: str) -> MessageView:
        """Guarda la pregunta, recupera fragmentos, responde y persiste respuesta y citas.

        Si la recuperación o el LLM fallan, la pregunta queda guardada y se propaga el error.
        """
        question = question.strip()
        if not question:
            raise ValueError("La pregunta está vacía.")

        with session_scope(self.session_factory) as session:
            conv = self._owned(session, user_id, conversation_id)
            session.add(Message(conversation_id=conversation_id, role="user", content=question))
            if conv.title == DEFAULT_TITLE:
                conv.title = _title_from(question)
            conv.updated_at = utcnow()

        chunks = self.rag.retrieve(question)
        answer = self.rag.answer(question, chunks)

        with session_scope(self.session_factory) as session:
            self._owned(session, user_id, conversation_id).updated_at = utcnow()
            known_ids = set(
                session.scalars(
                    select(Document.id).where(
                        Document.id.in_({c.document_id for c in chunks if c.document_id})
                    )
                )
            )
            message = Message(conversation_id=conversation_id, role="assistant", content=answer)
            message.citations = [
                MessageCitation(
                    document_id=c.document_id if c.document_id in known_ids else None,
                    position=i,
                    document_name=c.document_name,
                    page_start=c.page_start,
                    page_end=c.page_end,
                    chunk_type=c.chunk_type,
                    chunk_text=c.text,
                    score=c.score,
                )
                for i, c in enumerate(chunks, start=1)
            ]
            session.add(message)
            session.flush()
            session.refresh(message)
            return _message_view(message)
