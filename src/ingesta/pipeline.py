from langchain_core.documents import Document
from pymupdf import Document as PdfDocument

from src.ingesta.chunkeo import (
    chunkear,
    convertir_a_documentos_y_agregar_numero_paginas,
    documentos_de_tablas,
)
from src.ingesta.extraccion import extraer_pdf


def abrir_pdf(data: bytes) -> PdfDocument:
    return PdfDocument(stream=data, filetype="pdf")


def construir_documentos(data: bytes, nombre: str) -> list[Document]:
    """Extrae y fragmenta un PDF con la lógica de ingesta original.

    Devuelve los fragmentos de texto seguidos de las tablas, igual que el flujo
    previo de la página de subida.
    """
    pdf = abrir_pdf(data)
    try:
        texto, mapa_paginas, tablas = extraer_pdf(pdf)
    finally:
        pdf.close()
    chunks = chunkear(texto)
    documentos = convertir_a_documentos_y_agregar_numero_paginas(chunks, mapa_paginas, nombre)
    documentos += documentos_de_tablas(tablas, nombre)
    return documentos
