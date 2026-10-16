import hashlib
import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from src.config.settings import Settings
from src.db.models import Document, IngestionJob
from src.db.session import session_scope
from src.ingesta.pipeline import abrir_pdf, construir_documentos
from src.storage.files import LocalFileStorage
from src.vectorstore.embedding import embed_in_batches
from src.vectorstore.qdrant import QdrantRepository

logger = logging.getLogger(__name__)

PDF_MIME = "application/pdf"


class InvalidPDFError(ValueError):
    pass


class IngestionError(RuntimeError):
    pass


class DocumentNotFoundError(LookupError):
    pass


@dataclass(frozen=True)
class DocumentView:
    id: uuid.UUID
    original_name: str
    size_bytes: int
    uploaded_at: datetime
    sha256: str
    status: str
    chunk_count: int
    error_message: str | None
    uploaded_by: uuid.UUID | None


@dataclass(frozen=True)
class UploadResult:
    document: DocumentView
    duplicate: bool


def _view(doc: Document) -> DocumentView:
    return DocumentView(
        id=doc.id,
        original_name=doc.original_name,
        size_bytes=doc.size_bytes,
        uploaded_at=doc.uploaded_at,
        sha256=doc.sha256,
        status=doc.status,
        chunk_count=doc.chunk_count,
        error_message=doc.error_message,
        uploaded_by=doc.uploaded_by,
    )


def validate_pdf(data: bytes, max_bytes: int) -> int:
    """Valida el contenido real del archivo y devuelve su número de páginas."""
    if not data:
        raise InvalidPDFError("El archivo está vacío.")
    if len(data) > max_bytes:
        raise InvalidPDFError(f"El archivo supera el máximo de {max_bytes // (1024 * 1024)} MB.")
    if b"%PDF-" not in data[:1024]:
        raise InvalidPDFError("El contenido no es un PDF válido.")
    try:
        pdf = abrir_pdf(data)
    except Exception:
        raise InvalidPDFError("El PDF está dañado o no se puede abrir.") from None
    try:
        if not pdf.is_pdf:
            raise InvalidPDFError("El contenido no es un PDF válido.")
        if pdf.needs_pass:
            raise InvalidPDFError("El PDF está protegido con contraseña.")
        if pdf.page_count == 0:
            raise InvalidPDFError("El PDF no tiene páginas.")
        return pdf.page_count
    finally:
        pdf.close()


def _clean_filename(name: str) -> str:
    name = os.path.basename(name.replace("\\", "/")).strip() or "documento.pdf"
    return name[:255]


class DocumentService:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        storage: LocalFileStorage,
        repository: QdrantRepository,
        embedder,
        settings: Settings,
    ):
        self.session_factory = session_factory
        self.storage = storage
        self.repository = repository
        self.embedder = embedder
        self.settings = settings

    # ---- consulta -------------------------------------------------------
    def list_documents(self) -> list[DocumentView]:
        with session_scope(self.session_factory) as session:
            rows = session.scalars(select(Document).order_by(Document.uploaded_at.desc()))
            return [_view(d) for d in rows]

    def get(self, document_id: uuid.UUID) -> DocumentView | None:
        with session_scope(self.session_factory) as session:
            doc = session.get(Document, document_id)
            return _view(doc) if doc else None

    def get_pdf_bytes(self, document_id: uuid.UUID) -> bytes:
        with session_scope(self.session_factory) as session:
            doc = session.get(Document, document_id)
            if doc is None:
                raise DocumentNotFoundError(str(document_id))
            return self.storage.read(doc.storage_path)

    # ---- subida ---------------------------------------------------------
    def upload(
        self, data: bytes, filename: str, user_id: uuid.UUID | None = None, process: bool = True
    ) -> UploadResult:
        validate_pdf(data, self.settings.max_pdf_mb * 1024 * 1024)
        digest = hashlib.sha256(data).hexdigest()

        existing = self._find_by_hash(digest)
        if existing:
            return UploadResult(existing, duplicate=True)

        document_id = uuid.uuid4()
        storage_path = self.storage.path_for(document_id)
        try:
            with session_scope(self.session_factory) as session:
                doc = Document(
                    id=document_id,
                    original_name=_clean_filename(filename),
                    storage_path=storage_path,
                    size_bytes=len(data),
                    sha256=digest,
                    mime_type=PDF_MIME,
                    status="pending",
                    uploaded_by=user_id,
                )
                session.add(doc)
                session.flush()
                view = _view(doc)
        except IntegrityError:
            # otra sesión subió el mismo PDF entre la comprobación y el insert
            existing = self._find_by_hash(digest)
            if existing:
                return UploadResult(existing, duplicate=True)
            raise

        try:
            self.storage.save(storage_path, data)
        except Exception:
            self._drop_row(document_id)
            raise

        if process:
            view = self.process(document_id)
        return UploadResult(view, duplicate=False)

    def _find_by_hash(self, digest: str) -> DocumentView | None:
        with session_scope(self.session_factory) as session:
            doc = session.scalar(select(Document).where(Document.sha256 == digest))
            return _view(doc) if doc else None

    def _drop_row(self, document_id: uuid.UUID) -> None:
        with session_scope(self.session_factory) as session:
            doc = session.get(Document, document_id)
            if doc:
                session.delete(doc)

    # ---- procesamiento --------------------------------------------------
    def process(self, document_id: uuid.UUID) -> DocumentView:
        """Extrae, fragmenta, embebe e indexa. Sirve también para reintentar."""
        with session_scope(self.session_factory) as session:
            doc = session.get(Document, document_id)
            if doc is None:
                raise DocumentNotFoundError(str(document_id))
            if doc.status in ("ready", "deleting"):
                return _view(doc)
            attempt = (
                session.scalar(
                    select(func.count()).select_from(IngestionJob).where(
                        IngestionJob.document_id == document_id
                    )
                )
                or 0
            ) + 1
            job = IngestionJob(document_id=document_id, attempt=attempt)
            session.add(job)
            doc.status = "processing"
            doc.error_message = None
            session.flush()
            job_id, storage_path, name = job.id, doc.storage_path, doc.original_name

        try:
            data = self.storage.read(storage_path)
            documentos = construir_documentos(data, name)
            if not documentos:
                raise IngestionError("El PDF no contiene texto extraíble (¿es un escaneo?).")
            vectores = embed_in_batches(
                self.embedder,
                [d.page_content for d in documentos],
                self.settings.embedding_batch_size,
            )
            self.repository.delete_document(document_id)
            total = self.repository.upsert_document(document_id, documentos, vectores)
        except Exception as exc:
            logger.exception("Falló la ingesta del documento %s", document_id)
            self._cleanup_vectors(document_id)
            return self._finish(document_id, job_id, "failed", 0, str(exc) or type(exc).__name__)
        return self._finish(document_id, job_id, "ready", total, None)

    def _cleanup_vectors(self, document_id: uuid.UUID) -> None:
        try:
            self.repository.delete_document(document_id)
        except Exception:
            logger.exception("No se pudieron limpiar los vectores de %s", document_id)

    def _finish(
        self, document_id: uuid.UUID, job_id: uuid.UUID, status: str, chunks: int, error: str | None
    ) -> DocumentView:
        with session_scope(self.session_factory) as session:
            doc = session.get(Document, document_id)
            job = session.get(IngestionJob, job_id)
            if job:
                job.status = "succeeded" if status == "ready" else "failed"
                job.error = error
                job.finished_at = datetime.now(timezone.utc)
            if doc is None:  # eliminado mientras se procesaba
                self._cleanup_vectors(document_id)
                raise DocumentNotFoundError(str(document_id))
            doc.status = status
            doc.chunk_count = chunks
            doc.error_message = error[:1000] if error else None
            return _view(doc)

    def recover_stale(self) -> int:
        """Marca como fallidos los documentos que quedaron 'processing' tras un corte."""
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=self.settings.stale_processing_minutes)
        with session_scope(self.session_factory) as session:
            docs = session.scalars(
                select(Document).where(Document.status == "processing", Document.updated_at < cutoff)
            ).all()
            for doc in docs:
                doc.status = "failed"
                doc.error_message = "El procesamiento se interrumpió. Reintenta la ingesta."
            return len(docs)

    # ---- eliminación ----------------------------------------------------
    def delete(self, document_id: uuid.UUID) -> bool:
        """Elimina vectores, archivo y registro. Cada paso es idempotente.

        Si un paso falla, el documento queda en estado 'deleting' y se puede
        reintentar. Las citas históricas conservan su copia del fragmento.
        """
        with session_scope(self.session_factory) as session:
            doc = session.get(Document, document_id)
            if doc is None:
                return False
            doc.status = "deleting"
            storage_path = doc.storage_path

        self.repository.delete_document(document_id)
        self.storage.delete(storage_path)
        self._drop_row(document_id)
        return True
