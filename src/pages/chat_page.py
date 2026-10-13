import streamlit as st
from src.services.clients import get_llm, get_embedding
from src.vectorstore.qdrant import get_collection, get_qdrant_client, generate_reponse
from src.config.settings import COLECCION, K

def mostrar():
    st.title("QA Acreditación")
    st.set_page_config(page_title="QA Acreditación")

    # chat
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    store = get_collection(get_embedding(), COLECCION, get_qdrant_client())
    llm = get_llm()

    if prompt := st.chat_input("Escribe tu mensaje..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("Buscando información en el documento..."):
                try:
                    docs = store.similarity_search(prompt, k=K)
                    if not docs:
                        respuesta = "No se encuentra información relevante en el contexto."
                        st.markdown(respuesta)
                        st.session_state.messages.append({"role": "assistant", "content": respuesta})
                        st.stop()
                    else:
                        respuesta = generate_reponse(prompt, docs, llm)
                        st.markdown(respuesta)

                        paginas = sorted({
                            pagina for doc in docs
                            if (pagina := (doc.metadata.get("pagina_inicio"))) is not None
                        })

                        with st.expander("Fragmentos utilizados"):
                            if paginas:
                                st.write("Páginas consultadas: " + ", ".join(map(str, paginas)))

                            for i, doc in enumerate(docs, start=1):
                                st.markdown(f"**Fragmento {i}**")
                                st.text(doc.page_content)
                                if i < len(docs):
                                    st.divider()
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": respuesta
                        })              
                except Exception as e:
                    mensaje_error = (
                        f"Ha ocurrido un error al procesar la solicitud: {str(e)}"
                    )
                    st.error(mensaje_error)
                    st.session_state.messages.append({"role": "assistant", "content": mensaje_error})