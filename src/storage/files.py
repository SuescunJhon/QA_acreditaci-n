import os
import uuid
from pathlib import Path


class FileNotInStorageError(FileNotFoundError):
    pass


class LocalFileStorage:
    """Guarda los PDF originales en un directorio persistente del disco."""

    def __init__(self, base_dir: Path | str):
        self.base_dir = Path(base_dir).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _resolve(self, relative_path: str) -> Path:
        path = (self.base_dir / relative_path).resolve()
        if self.base_dir not in path.parents:
            raise ValueError("Ruta fuera del directorio de almacenamiento.")
        return path

    @staticmethod
    def path_for(document_id: uuid.UUID) -> str:
        hex_id = document_id.hex
        return f"{hex_id[:2]}/{hex_id}.pdf"

    def save(self, relative_path: str, data: bytes) -> None:
        path = self._resolve(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        with open(tmp, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)

    def read(self, relative_path: str) -> bytes:
        path = self._resolve(relative_path)
        if not path.is_file():
            raise FileNotInStorageError(relative_path)
        return path.read_bytes()

    def exists(self, relative_path: str) -> bool:
        return self._resolve(relative_path).is_file()

    def delete(self, relative_path: str) -> None:
        self._resolve(relative_path).unlink(missing_ok=True)
