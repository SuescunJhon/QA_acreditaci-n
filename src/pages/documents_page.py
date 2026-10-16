import pandas as pd
import streamlit as st

from src.container import Container
from src.pages.formatting import STATUS_LABELS, format_datetime, human_size
from src.services.auth import UserView
from src.services.documents import InvalidPDFError


def _upload_section(container: Container, user: UserView) -> None:
    key = f"uploader_{st.session_state.get('uploader_version', 0)}"
    files = st.file_uploader("Sube archivos PDF", type=["pdf"], accept_multiple_files=True, key=key)

    for level, text in st.session_state.pop("upload_results", []):
        getattr(st, level)(text)

    if files and st.button("Subir e indexar", type="primary"):
        results = []
        for f in files:
            with st.spinner(f"Procesando {f.name}..."):
                try:
                    result = container.documents.upload(f.getvalue(), f.name, user.id)
                except InvalidPDFError as exc:
                    results.append(("error", f"**{f.name}**: {exc}"))
                    continue
                except Exception as exc:
                    results.append(("error", f"**{f.name}**: error inesperado ({exc})"))
                    continue
            doc = result.document
            if result.duplicate:
                results.append(("warning", f"**{f.name}** ya existe como «{doc.original_name}»."))
            elif doc.status == "ready":
                results.append(("success", f"**{f.name}** indexado ({doc.chunk_count} fragmentos)."))
            else:
                results.append(("error", f"**{f.name}** no se pudo indexar: {doc.error_message}"))
        st.session_state["upload_results"] = results
        st.session_state["uploader_version"] = st.session_state.get("uploader_version", 0) + 1
        st.rerun()


def _detail(container: Container, user: UserView, docs) -> None:
    selected = st.selectbox(
        "Documento",
        docs,
        format_func=lambda d: f"{d.original_name} · {format_datetime(d.uploaded_at)}",
        index=None,
        placeholder="Selecciona un documento para ver sus acciones",
    )
    if selected is None:
        return

    if selected.error_message:
        st.error(selected.error_message)

    cols = st.columns(3)
    try:
        pdf_bytes = container.documents.get_pdf_bytes(selected.id)
    except FileNotFoundError:
        pdf_bytes = None
        st.error("El archivo original no se encuentra en el almacenamiento.")

    if pdf_bytes is not None:
        cols[0].download_button(
            "⬇️ Descargar", pdf_bytes, file_name=selected.original_name, mime="application/pdf"
        )
    if selected.status in ("failed", "pending", "processing") and cols[1].button("🔁 Reintentar"):
        with st.spinner("Procesando..."):
            container.documents.process(selected.id)
        st.rerun()

    if user.is_admin:
        with cols[2].popover("🗑️ Eliminar"):
            st.warning("Se borrarán el PDF, sus vectores y su registro. Las citas antiguas se conservan.")
            if st.button("Confirmar eliminación", type="primary"):
                container.documents.delete(selected.id)
                st.rerun()

    if pdf_bytes is not None and st.toggle("Previsualizar PDF"):
        st.pdf(pdf_bytes, height=650)


def mostrar(container: Container, user: UserView) -> None:
    st.title("Gestor de documentos")
    _upload_section(container, user)

    docs = container.documents.list_documents()
    if not docs:
        st.info("Todavía no hay documentos.")
        return

    st.dataframe(
        pd.DataFrame(
            {
                "Nombre": d.original_name,
                "Tamaño": human_size(d.size_bytes),
                "Subido": format_datetime(d.uploaded_at),
                "Estado": STATUS_LABELS.get(d.status, d.status),
                "Fragmentos": d.chunk_count,
            }
            for d in docs
        ),
        hide_index=True,
        use_container_width=True,
    )
    _detail(container, user, docs)
