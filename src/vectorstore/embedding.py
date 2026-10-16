from typing import Protocol, Sequence


class Embedder(Protocol):
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...


def embed_in_batches(embedder: Embedder, texts: Sequence[str], batch_size: int = 64) -> list[list[float]]:
    vectors: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        vectors.extend(embedder.embed_documents(list(texts[i : i + batch_size])))
    return vectors
