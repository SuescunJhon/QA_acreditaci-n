import streamlit as st
import uuid
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
import pymupdf4llm
from pymupdf import Document as pymuDocument 
import re
from langchain_text_splitters import RecursiveCharacterTextSplitter
import tiktoken
from langchain_core.documents import Document
import time
from openai import OpenAI


# configuraciones
DIMENSION_EMBEDDING = 3072
CHUNK_SIZE = 800
CHUNK_OVERLAP = 0
MODELO_EMBEDDING = "openai/text-embedding-3-large"
COLECCION = "pdfs_acreditacion"



PATRON_TABLA_MD = re.compile(
    r'(^\|.*\|\s*\n'
    r'(?:\|[ \t]*:?-+:?[ \t]*\|.*\n)'
    r'(?:\|.*\|\s*\n?)+)',
    re.MULTILINE,
)

# variables de entorno


# funciones utiles
def separar_tablas(texto, numero_pagina):
    tablas_encontradas = PATRON_TABLA_MD.findall(texto)
    tablas = [
        {
            "numero_pagina": numero_pagina,
            "contenido_md": tabla.strip(),
        }
        for tabla in tablas_encontradas
    ]
    contador = {"i": 0}
    
    def reemplazo(match):
        contador["i"] += 1

        return (
            f"\n[tabla {contador['i']} "
            f"de la pagina {numero_pagina}]\n"
        )

    texto_sin_tablas = PATRON_TABLA_MD.sub(
        reemplazo,
        texto
    )

    return texto_sin_tablas, tablas

def paginas_de_rango(mapa_paginas, inicio, fin):
    paginas = [n for (a, b, n) in mapa_paginas if a < fin and b > inicio and n is not None]
    return paginas or [None]

def chunkear(texto, mapa_paginas, file_name):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=lambda text: len(tiktoken.get_encoding("cl100k_base").encode(text)),
        add_start_index=True,
    )
    chunks = splitter.create_documents([texto])

    documentos = []
    for chunk in chunks:
        inicio = chunk.metadata.get("start_index", 0)
        fin = inicio + len(chunk.page_content)
        paginas = [p for p in paginas_de_rango(mapa_paginas, inicio, fin) if p is not None]
        documentos.append(Document(
            page_content=chunk.page_content,
            metadata={
                "tipo": "texto",
                "pagina_inicio": min(paginas) if paginas else None,
                "pagina_fin": max(paginas) if paginas else None,
                "fuente": file_name,
            },
        ))
    return documentos

def documentos_de_tablas(tablas, file_name):
    return [
        Document(
            page_content=t["contenido_md"],
            metadata={"tipo": "tabla", "pagina": t["numero_pagina"], "fuente": file_name, "indice_tabla": t["indice"]},
        )
        for t in tablas
    ]

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



def embeber(textos, tam_lote = 96):
    if not textos:
        return []
    vectores = []
    for i in range(0, len(textos), tam_lote):
        lote = textos[i:i + tam_lote]
        resp = con_reintentos(lambda: openai.embeddings.create(model=MODELO_EMBEDDING, input=lote))
        vectores.extend([d.embedding for d in resp.data])
    return vectores


# clientes
qdrant = QdrantClient(
            api_key=st.secrets["QDRANT_API_KEY"],
            url=st.secrets["QDRANT_URL"]
        )



st.title("Gestor de Documentos")

file = st.file_uploader("Sube tu archivo PDF", type=["pdf"])

if file:
    st.success(f"Archivo seleccionado: **{file.name}**")
    doc = pymuDocument(stream=file.getvalue(), filetype="pdf")
    index_document = st.button("Indexar PDF", type="primary", use_container_width=True)

    if index_document:
        st.subheader("1. Extracción del PDF")
        with st.spinner("Procesando el PDF..."):
            pages = pymupdf4llm.to_markdown(
                doc=doc,
                page_chunks=True,
                table_strategy="lines_strict",
                header=False,
                footer=False,   
            )

            text_parts  = []
            page_map = []
            text_length = 0
        
            for page in pages:
                metadata = page.get("metadata", {})
                page_number = metadata.get("page", metadata.get("page_number", None))
                texto_without_tables, tables = separar_tablas(page.get("text", ""), page_number)

                if text_parts :
                    text_parts.append(" ")
                    text_length += 1
                inicio = text_length
                text_parts.append(texto_without_tables)
                text_length += len(texto_without_tables)
                page_map.append((inicio, text_length, page_number))

            for i, table in enumerate(tables):
                table["indice"] = i

            text = "".join(text_parts)

        st.success("PDF procesado correctamente.")

        st.subheader("2. Creación de Chunks")
        with st.spinner("Creando chunks..."):
            documentos = chunkear(text, page_map, file.name) + documentos_de_tablas(tables, file.name)
        st.success(f"{len(documentos)} documentos (texto + tablas)")

        st.subheader("3. Generación de Embeddings")
        with st.spinner("Generando embeddings..."):
            vectores = embeber([d.page_content for d in documentos])
        st.success(f"{len(vectores)} embeddings generados.")

        st.subheader("4. Indexación en Qdrant Cloud")
        with st.spinner("Indexando en Qdrant Cloud..."):
            if not qdrant.collection_exists(COLECCION):
                qdrant.create_collection(
                    collection_name=COLECCION,
                    vectors_config=VectorParams(size=DIMENSION_EMBEDDING, distance=Distance.COSINE),
                )
            puntos = [
                PointStruct(id=str(uuid.uuid4()), vector=v, payload={"page_content": d.page_content, **d.metadata})
                for d, v in zip(documentos, vectores)
            ]
            qdrant.upsert(collection_name=COLECCION, points=puntos)
        st.success(f"Indexación completada en la colección '{COLECCION}' de Qdrant Cloud. {len(puntos)} puntos indexados.")