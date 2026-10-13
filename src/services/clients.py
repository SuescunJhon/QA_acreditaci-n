from langchain_openrouter.chat_models import ChatOpenRouter
import streamlit as st
from src.config.settings import MODELO_LLM, MODELO_EMBEDDING
from langchain_openai import OpenAIEmbeddings

def get_llm():
    api_key = st.secrets.get("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("No se encontró la variable de entorno OPENROUTER_API_KEY.")
    return ChatOpenRouter(
        model = MODELO_LLM,
        api_key = api_key,
    )

def get_embedding():
    return OpenAIEmbeddings(
        model=MODELO_EMBEDDING,
        base_url="https://openrouter.ai/api/v1",
        api_key=st.secrets.get("OPENROUTER_API_KEY")
    )