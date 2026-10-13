from langchain_text_splitters import RecursiveCharacterTextSplitter
from src.config.settings import CHUNK_SIZE, CHUNK_OVERLAP
from langchain_core.documents import Document

def _obtener_paginas_del_chunk(inicio_chunk, fin_chunk, mapa_paginas):
    paginas = [
        pagina
        for pagina_inicio, pagina_final, pagina in mapa_paginas
        if inicio_chunk <= pagina_final and fin_chunk >= pagina_inicio
    ]

    if not paginas:
        return None, None
    
    return min(paginas), max(paginas)

def chunkear(texto):
    splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        encoding_name="cl100k_base",
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    return splitter.split_text(texto)

def convertir_a_documentos_y_agregar_numero_paginas(chunks, mapa_paginas, pdf_name):
    documentos = []
    inicio = 0
    for chunk in chunks:
        fin = inicio + len(chunk)
        pagina_inicio, pagina_final = _obtener_paginas_del_chunk(inicio, fin, mapa_paginas)
        documentos.append(Document(
            page_content=chunk,
            metadata = {
                "tipo": "texto",
                "pagina_inicio": pagina_inicio,
                "pagina_fin": pagina_final,
                "fuente": pdf_name
            }
        ))
        inicio = fin + 1
    return documentos

def documentos_de_tablas(tables, pdf_name):
    return [
        Document(
            page_content=t["contenido_md"],
            metadata={
                "tipo": "tabla", 
                "pagina": t["numero_pagina"], 
                "fuente": pdf_name, 
                "indice_tabla": t["indice"]},
        )
        for t in tables
    ]