# QA Acreditación

Aplicación web RAG para consultar documentos PDF de factores de acreditación de la EISC.
Stack: Streamlit, LangChain, OpenRouter (LLM y embeddings), Qdrant (vectores) y PostgreSQL
(usuarios, documentos, conversaciones y citas). Los PDF originales se guardan en disco.

## Funcionalidades

- **Chat RAG** con conversaciones persistentes por usuario. Cada respuesta muestra sus fuentes:
  PDF, página y texto exacto del fragmento. Las citas se guardan por valor, así que se conservan
  aunque el documento se elimine después.
- **Gestor de PDF**: solo PDF (se valida el contenido, no solo la extensión), detección de
  duplicados por SHA-256, estado de procesamiento, número de fragmentos, previsualización,
  descarga, reintento de ingestas fallidas y eliminación completa (PDF en disco, vectores en
  Qdrant y registro en PostgreSQL).
- **Usuarios** (pensado para unas 10 personas): login con contraseña (bcrypt). Cada usuario ve solo
  sus conversaciones; los documentos son compartidos. Cualquier usuario puede subir PDF; solo el
  administrador elimina documentos y gestiona usuarios.

## Requisitos

- Python 3.12+ y [uv](https://docs.astral.sh/uv/)
- PostgreSQL 14+ accesible en local
- Una clave de [OpenRouter](https://openrouter.ai)
- Qdrant: no hace falta instalar nada. Por defecto se usa el modo embebido en `data/qdrant`.
  Para un servidor propio, define `QDRANT_URL`.

## Puesta en marcha

```powershell
uv sync

# 1. Base de datos (en psql como superusuario)
#    CREATE USER qa WITH PASSWORD '........';
#    CREATE DATABASE qa_acreditacion OWNER qa;

# 2. Configuración
copy .env.example .env      # y edita OPENROUTER_API_KEY y DATABASE_URL

# 3. Migraciones y primer administrador
uv run python -m src.cli migrate
uv run python -m src.cli create-user admin --role admin

# 4. Ejecutar
uv run streamlit run app.py
```

Más usuarios: desde la página **Usuarios** (admin) o con `uv run python -m src.cli create-user NOMBRE`.
La configuración se lee de variables de entorno o de `.env` (ver `.env.example`); `st.secrets`
ya no se usa.

## Estructura

```
app.py                  entrada: login y navegación
src/config/             ajustes (pydantic-settings) y prompt
src/db/                 modelos SQLAlchemy y sesiones
migrations/             migraciones Alembic (alembic.ini en la raíz)
src/storage/            almacenamiento de PDF en disco
src/ingesta/            extracción y chunkeo (lógica original) + pipeline
src/vectorstore/        repositorio Qdrant y embeddings por lotes
src/services/           auth, documentos, RAG y chat
src/pages/              páginas de Streamlit
tests/                  pruebas
```

## Esquema de PostgreSQL

`users`, `documents` (UUID, nombre, ruta, tamaño, SHA-256 único, MIME, estado, nº de fragmentos,
fechas), `ingestion_jobs` (intentos y errores de cada ingesta), `conversations`, `messages` y
`message_citations`. Estados de documento: `pending`, `processing`, `ready`, `failed`, `deleting`.

## Ingesta y eliminación

Subida: validar PDF → SHA-256 (duplicado = no se procesa) → guardar archivo → registrar → extraer →
fragmentar → embeddings → Qdrant. Si falla, el documento queda `failed`, se limpian sus vectores y
se puede reintentar. Los documentos que quedan en `processing` tras un corte se marcan `failed`
al arrancar. La eliminación borra vectores, archivo y registro; si un paso falla el documento
queda `deleting` y se puede repetir.

Si cambias `EMBEDDING_MODEL` o `EMBEDDING_DIMENSION`, usa otra `QDRANT_COLLECTION` y reindexa.

## Pruebas

```powershell
uv run pytest
```

Las pruebas usan SQLite, Qdrant en memoria y embeddings/LLM simulados: no necesitan red,
PostgreSQL ni claves. **No ejecutan nada contra PostgreSQL ni OpenRouter reales.**
