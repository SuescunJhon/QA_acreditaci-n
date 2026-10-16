import streamlit as st

st.set_page_config(page_title="QA Acreditación", page_icon=":material/school:", layout="wide")

from src.config.settings import get_settings  # noqa: E402
from src.container import Container, build_container  # noqa: E402
from src.pages import chat_page, documents_page, login, users_page  # noqa: E402


@st.cache_resource(show_spinner="Iniciando...")
def get_container() -> Container:
    container = build_container(get_settings())
    container.documents.recover_stale()
    return container


def main() -> None:
    try:
        container = get_container()
        user = st.session_state.get("user")
        if user is not None:
            user = container.auth.get(user.id)  # refleja desactivaciones y cambios de rol
            st.session_state["user"] = user
    except Exception as exc:
        st.error(
            f"No se pudo iniciar la aplicación: {exc}\n\n"
            "Comprueba el archivo `.env` y que las migraciones estén aplicadas "
            "(`uv run python -m src.cli migrate`)."
        )
        st.stop()

    if user is None:
        login.mostrar(container)
        return

    pages = [
        st.Page(lambda: chat_page.mostrar(container, user), title="Chat", icon=":material/chat:", url_path="chat", default=True),
        st.Page(lambda: documents_page.mostrar(container, user), title="Documentos", icon=":material/description:", url_path="documentos"),
    ]
    if user.is_admin:
        pages.append(
            st.Page(lambda: users_page.mostrar(container, user), title="Usuarios", icon=":material/group:", url_path="usuarios")
        )

    with st.sidebar:
        st.caption(f"Sesión: **{user.username}** ({user.role})")
        if st.button("Cerrar sesión"):
            st.session_state.clear()
            st.rerun()
    st.navigation(pages).run()


main()
