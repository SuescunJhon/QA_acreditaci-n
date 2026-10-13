# qdrant
COLECCION = "pdfs_acreditacion"

# chunking
CHUNK_SIZE = 800
CHUNK_OVERLAP = 0

#embedding
MODELO_EMBEDDING = "openai/text-embedding-3-large"
DIMENSION_EMBEDDING = 3072

# recuperación y respuesta
K = 5
MODELO_LLM = "anthropic/claude-sonnet-5"

PROMPT_ESTRUCTURADO = """Eres un asistente que responde preguntas basandote ESTRICTAMENTE en el contexto proporcionado, sin usar conocimiento externo. Sigue estos pasos antes de responder:

1. Identifica que fragmentos del contexto son relevantes para la pregunta.
2. Verifica si, con esos fragmentos, la pregunta se puede responder de forma completa, parcial, o no se puede responder.
3. Redacta la respuesta final basandote unicamente en lo que identificaste en el paso 1.

Contexto:
{contexto}

Pregunta: {pregunta}

Responde siguiendo EXACTAMENTE este formato:
Fragmentos relevantes: <cuales y por que, brevemente>
Cobertura: <completa / parcial / nula>
Respuesta final: <tu respuesta aqui; si la cobertura es nula, escribe "No se encuentra en el contexto">"""