import streamlit as st

from src.container import Container


def mostrar(container: Container) -> None:
    st.title("QA Acreditación")
    if container.auth.count_users() == 0:
        st.warning(
            "No hay usuarios. Crea el primer administrador con:\n\n"
            "`uv run python -m src.cli create-user admin --role admin`"
        )
        return

    with st.form("login"):
        username = st.text_input("Usuario")
        password = st.text_input("Contraseña", type="password")
        submitted = st.form_submit_button("Iniciar sesión", type="primary")

    if submitted:
        user = container.auth.authenticate(username, password)
        if user is None:
            st.error("Usuario o contraseña incorrectos.")
        else:
            st.session_state["user"] = user
            st.rerun()
