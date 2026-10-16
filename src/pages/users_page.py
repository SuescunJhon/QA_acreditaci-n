import streamlit as st

from src.container import Container
from src.services.auth import AuthError, UserView


def mostrar(container: Container, user: UserView) -> None:
    st.title("Usuarios")

    with st.form("new_user", clear_on_submit=True):
        st.subheader("Crear usuario")
        username = st.text_input("Usuario")
        password = st.text_input("Contraseña", type="password")
        role = st.selectbox("Rol", ["user", "admin"])
        if st.form_submit_button("Crear", type="primary"):
            try:
                container.auth.create_user(username, password, role)
                st.success(f"Usuario '{username.strip().lower()}' creado.")
            except AuthError as exc:
                st.error(str(exc))

    st.subheader("Usuarios existentes")
    for u in container.auth.list_users():
        c1, c2, c3 = st.columns([3, 1, 2])
        c1.markdown(f"**{u.username}**" + ("" if u.is_active else " _(inactivo)_"))
        c2.write(u.role)
        if u.id != user.id:
            label = "Desactivar" if u.is_active else "Activar"
            if c3.button(label, key=f"toggle_{u.id}"):
                try:
                    container.auth.set_active(u.id, not u.is_active)
                    st.rerun()
                except AuthError as exc:
                    st.error(str(exc))
