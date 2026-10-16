from datetime import datetime, timezone

STATUS_LABELS = {
    "pending": "⏳ Pendiente",
    "processing": "⚙️ Procesando",
    "ready": "✅ Listo",
    "failed": "❌ Falló",
    "deleting": "🗑️ Eliminando",
}


def human_size(size_bytes: int) -> str:
    size = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{int(size)} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size_bytes} B"


def to_local(dt: datetime) -> datetime:
    if dt.tzinfo is None:  # SQLite devuelve fechas sin zona; se guardan en UTC
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone()


def format_datetime(dt: datetime) -> str:
    return to_local(dt).strftime("%Y-%m-%d %H:%M")
