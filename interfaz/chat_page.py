import streamlit as st
from langchain_openrouter.chat_models import ChatOpenRouter
import time
from openai import OpenAI
from qdrant_client import QdrantClient
import re

# configuraciones
COLECCION = "pdfs_acreditacion"
K = 5
MODELO_LLM = "anthropic/claude-sonnet-5"
MODELO_EMBEDDING = "openai/text-embedding-3-large"
PROMPT_ESTRUCTURADO = """Eres un asistente que responde preguntas basandote ESTRICTAMENTE en el contexto proporcionado, sin usar conocimiento externo. Sigue estos pasos antes de responder:

1. Identifica que fragmentos del contexto son relevantes para la pregunta.
2. Verifica si, con esos fragmentos, la pregunta se puede responder de forma completa, parcial, o no se puede responder.
3. Redacta la respuesta final basandote unicamente en lo que identificaste en el paso 1.

Contexto:
{contexto}

Pregunta: {pregunta}

Responde siguiendo EXACTAMENTE este formato:
Fragmentos relevantes: <cuales y por que, brevemente>
Cobertura: <completa / parcial / nula>
Respuesta final: <tu respuesta aqui; si la cobertura es nula, escribe "No se encuentra en el contexto">"""


# funciones
def con_reintentos(func, intentos=3, espera=5):
    """reintenta con backoff, sin fallback a otro modelo (aqui no aplica ese problema
    porque esto ya no es una comparacion, es el pipeline final)"""
    for i in range(intentos):
        try:
            return func()
        except Exception as e:
            if i == intentos - 1:
                raise
            print(f"  fallo ({e}), reintento en {espera}s...")
            time.sleep(espera)
            espera *= 2


openai = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=st.secrets["OPENROUTER_API_KEY"])
qdrant = QdrantClient(
            api_key=st.secrets["QDRANT_API_KEY"],
            url=st.secrets["QDRANT_URL"]
        )

def embeber(textos, tam_lote = 96):
    if not textos:
        return []
    vectores = []
    for i in range(0, len(textos), tam_lote):
        lote = textos[i:i + tam_lote]
        resp = con_reintentos(lambda: openai.embeddings.create(model=MODELO_EMBEDDING, input=lote))
        vectores.extend([d.embedding for d in resp.data])
    return vectores

def recuperar(qdrant, pregunta):
    vector = embeber([pregunta])[0]
    return qdrant.query_points(collection_name=COLECCION, query=vector, limit=K, with_payload=True).points

def formatear_contexto(hits):
    return "\n\n".join(f"--- Fragmento {i + 1} ---\n{h.payload['page_content']}" for i, h in enumerate(hits))


def extraer_campo(texto, etiqueta):
    m = re.search(rf"{etiqueta}:\s*(.*?)(?:\n[A-ZÁÉÍÓÚ][a-záéíóú ]+:|\Z)", texto, re.DOTALL)
    return m.group(1).strip() if m else ""


def generar(pregunta: str, hits) -> str:
    prompt = PROMPT_ESTRUCTURADO.format(contexto=formatear_contexto(hits), pregunta=pregunta)
    resp = con_reintentos(lambda: openai.chat.completions.create(
        model=MODELO_LLM,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    ))
    return resp.choices[0].message.content


llm = ChatOpenRouter(
        model = MODELO_LLM,
        temperature = 0.5,
        api_key = st.secrets["OPENROUTER_API_KEY"],
    )

st.title("QA Acreditación")
st.set_page_config(page_title="QA Acreditación")

# chat
if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Escribe tu mensaje..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        with st.spinner("Buscando información en el documento..."):
            try:
                hits = recuperar(qdrant, prompt)
                if not hits:
                    respuesta = "No se encuentra información relevante en el contexto."
                    st.markdown(respuesta)
                    st.session_state.messages.append({"role": "assistant", "content": respuesta})
                    st.stop()
                salida = generar(prompt, hits)
                cobertura = extraer_campo(salida, "Cobertura")
                respuesta = extraer_campo(salida, "Respuesta final")
                if not respuesta:
                    respuesta = salida.strip()
                if cobertura and cobertura.lower() != "completa":
                    st.caption(f"Cobertura: {cobertura}")
                st.markdown(respuesta)
                paginas = sorted({
                    hit.payload.get("pagina_inicio")
                    or hit.payload.get("pagina")
                    for hit in hits
                } - {None})
                if paginas:
                    with st.expander("Framentos utilizados"):
                        st.write(f"Páginas consultadas: {', '.join(map(str, paginas))}")
                        for i, hit in enumerate(hits):
                            contenido = hit.payload.get("page_content", "")
                            score = getattr(hit, "score", None)
                            st.markdown(f"**Fragmento {i + 1}**")
                            if score is not None:
                                st.caption(f"Similitud: {score:.4f}")
                            st.text(contenido)
                            if i < len(hits) - 1:
                                st.divider()
                st.session_state.messages.append({"role": "assistant", "content": respuesta})                
            except Exception as e:
                mensaje_error = (
                    f"Ha ocurrido un error al procesar la solicitud: {str(e)}"
                )
                st.error(mensaje_error)
                st.session_state.messages.append({"role": "assistant", "content": mensaje_error})