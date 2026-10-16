from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import Runnable

from src.config.template_prompt import template
from src.vectorstore.qdrant import QdrantRepository, RetrievedChunk

SIN_CONTEXTO = "No se encuentra información relevante en el contexto."


def formatear_contexto(chunks: list[RetrievedChunk]) -> str:
    partes = []
    for i, chunk in enumerate(chunks, start=1):
        pagina = ""
        if chunk.page_start is not None:
            pagina = f", pág. {chunk.page_start}"
            if chunk.page_end not in (None, chunk.page_start):
                pagina += f"-{chunk.page_end}"
        partes.append(f"[Fragmento {i}] ({chunk.document_name}{pagina})\n{chunk.text}")
    return "\n\n".join(partes)


class RagService:
    def __init__(self, embedder, repository: QdrantRepository, llm: Runnable, k: int):
        self.embedder = embedder
        self.repository = repository
        self.llm = llm
        self.k = k

    def retrieve(self, question: str) -> list[RetrievedChunk]:
        vector = self.embedder.embed_query(question)
        return self.repository.search(vector, self.k)

    def answer(self, question: str, chunks: list[RetrievedChunk]) -> str:
        if not chunks:
            return SIN_CONTEXTO
        chain = template | self.llm | StrOutputParser()
        return chain.invoke({"pregunta": question, "contexto": formatear_contexto(chunks)})
