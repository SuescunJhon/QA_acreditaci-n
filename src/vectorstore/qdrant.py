from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct
import streamlit as st
from langchain_qdrant import QdrantVectorStore
import uuid
from src.config.template_prompt import template
from langchain_core.output_parsers import StrOutputParser

def get_qdrant_client():
    url = st.secrets.get("QDRANT_URL")
    api_key = st.secrets.get("QDRANT_API_KEY")
    if not url:
        raise ValueError("No se encontró la variable de entorno QDRANT_URL.")
    if not api_key:
        raise ValueError("No se encontró la variable de entorno QDRANT_API_KEY")
    return QdrantClient(url=url, api_key=api_key)

def create_collection_if_not_exist(client, collection_name):
    client = get_qdrant_client()
    if not client.collection_exists(collection_name):
        client.create_collection(collection_name)

def get_collection(embeddings, collection_name,client):
    return QdrantVectorStore(
    embedding=embeddings,
    collection_name=collection_name,
    client = client
    )

def create_points(vectors, documents):
    return [
        PointStruct(id=uuid.uuid4(), vector=v, payload={"page_content": d.page_content, **d.metadata})
        for d, v in zip(documents, vectors)
    ]

def insert_to_collection(client, points, collection_name):
    client.upsert(collection_name, points)

def _formatear_contexto(docs) -> str:
    return "\n\n".join(
        f"[Fragmento {i}]\n{doc.page_content}"
        for i, doc in enumerate(docs, start=1)
    )

def generate_reponse(query, docs, llm):
    if not docs:
        return "No se encuentra información relevante en el contexto"

    cadena = template | llm | StrOutputParser()
    return cadena.invoke({
        "pregunta": query,
        "contexto": _formatear_contexto(docs)
    })