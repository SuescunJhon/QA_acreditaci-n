import pymupdf4llm
import re

_PATRON_TABLA_MD = re.compile(
    r'(^\|.*\|\s*\n'
    r'(?:\|[ \t]*:?-+:?[ \t]*\|.*\n)'
    r'(?:\|.*\|\s*\n?)+)',
    re.MULTILINE,
)

def _procesar_pagina(texto, num_pagina):
    contador = 0
    tablas = []

    def remplazo(match):
        nonlocal contador
        contador += 1
        tablas.append({"numero_pagina": num_pagina, "contenido_md": match.group(0).strip()})
        return f"\n[tabla {contador['i']} de la pagina {num_pagina}]\n"

    texto_sin_tablas = _PATRON_TABLA_MD.sub(remplazo, texto)
    return texto_sin_tablas, tablas

def _procesar_paginas(paginas):
    textos = []
    mapa_paginas = []
    caracteres_recorridos = 0
    tablas = []

    for pagina in paginas:
            metadata = pagina.get("metadata", {})
            numero_pagina = metadata.get("page_number", None)
            texto_sin_tablas, tablas_pagina = _procesar_pagina(pagina.get("text", ""), numero_pagina)
            tablas.extend(tablas_pagina)
    
            if textos:
                textos.append(" ")
                caracteres_recorridos += 1
            inicio = caracteres_recorridos
            textos.append(texto_sin_tablas)
            caracteres_recorridos += len(texto_sin_tablas)
            mapa_paginas.append((inicio, caracteres_recorridos, numero_pagina))
    
    for i, t in enumerate(tablas):
        t["indice"] = i

    return "".join(textos), mapa_paginas, tablas


def extraer_pdf(pdf):
    paginas = pymupdf4llm.to_markdown(
        pdf, page_chunks=True, table_strategy="lines_strict", header=False, footer=False
    )
    return _procesar_paginas(paginas)