import streamlit as st
from pymupdf import Document as pymuDocument 
from src.ingesta.extraccion import extraer_pdf
from src.ingesta.chunkeo import chunkear, convertir_a_documentos_y_agregar_numero_paginas, documentos_de_tablas
from src.vectorstore.embedding import embedding
from src.vectorstore.qdrant import get_qdrant_client, create_collection_if_not_exist, create_points, insert_to_collection
from src.config.settings import COLECCION

def mostrar():
    st.title("Gestor de Documentos")

    file = st.file_uploader("Sube tu archivo PDF", type=["pdf"])

    if file:
        st.success(f"Archivo seleccionado: **{file.name}**")
        doc = pymuDocument(stream=file.getvalue(), filetype="pdf")
        index_document = st.button("Indexar PDF", type="primary", use_container_width=True)

        if index_document:
            st.subheader("1. Extracción del PDF")
            with st.spinner("Procesando el PDF..."):
                text, page_map, tables = extraer_pdf(doc)
            st.success("PDF procesado correctamente.")

            st.subheader("2. Creación de Chunks")
            with st.spinner("Creando chunks..."):
                chunks = chunkear(text)
                documentos = convertir_a_documentos_y_agregar_numero_paginas(chunks, page_map, file.name)
                documentos += documentos_de_tablas(tables, file.name)
            st.success(f"{len(documentos)} documentos (texto + tablas)")

            st.subheader("3. Generación de Embeddings")
            with st.spinner("Generando embeddings..."):
                vectores = embedding(chunks)
            st.success(f"{len(vectores)} embeddings generados.")

            st.subheader("4. Indexación en Qdrant Cloud")
            with st.spinner("Indexando en Qdrant Cloud..."):
                qdrant_client = get_qdrant_client()
                create_collection_if_not_exist(qdrant_client, COLECCION)
                puntos = create_points(vectores, documentos)
                insert_to_collection(qdrant_client, puntos, COLECCION)
            st.success(f"Indexación completada en la colección '{COLECCION}' de Qdrant Cloud. {len(puntos)} puntos indexados.")