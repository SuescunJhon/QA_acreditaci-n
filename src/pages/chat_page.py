import streamlit as st

from src.container import Container
from src.services.auth import UserView
from src.services.chat import CitationView, ConversationNotFoundError


def _render_citations(citations: list[CitationView]) -> None:
    if not citations:
        return
    with st.expander(f"Fuentes ({len(citations)})"):
        for i, c in enumerate(citations):
            header = f"**[{c.position}] {c.document_name}**"
            if c.pages_label:
                header += f" · pág. {c.pages_label}"
            if c.chunk_type == "tabla":
                header += " · tabla"
            st.markdown(header)
            if c.document_id is None:
                st.caption("El documento original ya no está disponible.")
            st.text(c.chunk_text)
            if i < len(citations) - 1:
                st.divider()


def _sidebar(container: Container, user: UserView) -> None:
    with st.sidebar:
        if st.button(":material/edit_square: Nuevo chat", use_container_width=True):
            st.session_state["conversation_id"] = None
            st.rerun()
        st.caption("Conversaciones")
        current = st.session_state.get("conversation_id")
        for conv in container.chat.list_conversations(user.id):
            col_open, col_del = st.columns([5, 1])
            if col_open.button(
                conv.title,
                key=f"open_{conv.id}",
                use_container_width=True,
                type="primary" if conv.id == current else "tertiary",
            ):
                st.session_state["conversation_id"] = conv.id
                st.rerun()
            if col_del.button(":material/delete:", key=f"del_{conv.id}", help="Eliminar conversación", type="tertiary"):
                container.chat.delete_conversation(user.id, conv.id)
                if conv.id == current:
                    st.session_state["conversation_id"] = None
                st.rerun()


def mostrar(container: Container, user: UserView) -> None:
    st.title("Chat")
    _sidebar(container, user)

    conversation_id = st.session_state.get("conversation_id")
    messages = []
    if conversation_id:
        try:
            messages = container.chat.get_messages(user.id, conversation_id)
        except ConversationNotFoundError:
            st.session_state["conversation_id"] = conversation_id = None

    for message in messages:
        with st.chat_message(message.role):
            st.markdown(message.content)
            _render_citations(message.citations)

    if error := st.session_state.pop("chat_error", None):
        st.error(error)

    if question := st.chat_input("Escribe tu pregunta sobre los documentos..."):
        with st.chat_message("user"):
            st.markdown(question)
        try:
            if conversation_id is None:
                conversation_id = container.chat.create_conversation(user.id).id
                st.session_state["conversation_id"] = conversation_id
            with st.chat_message("assistant"):
                with st.spinner("Buscando información en los documentos..."):
                    container.chat.ask(user.id, conversation_id, question)
        except Exception as exc:
            st.session_state["chat_error"] = f"Ha ocurrido un error al procesar la solicitud: {exc}"
        st.rerun()
