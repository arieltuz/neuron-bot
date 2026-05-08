"""
Módulo de reconocimiento de voz con OpenAI Whisper
"""

import os
import re
import logging
import tempfile
from typing import Optional

logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.environ.get(
    "OPENAI_API_KEY",
    "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"
)

# NO instanciamos OpenAI a nivel de módulo — se crea dentro de la función
# para evitar errores de compatibilidad con httpx al importar

async def transcribir_audio(file_bytes: bytes, extension: str = "ogg") -> str:
    """Transcribe audio con Whisper en español."""
    # Importación y creación del cliente dentro de la función
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)

    with tempfile.NamedTemporaryFile(suffix=f".{extension}", delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name
    try:
        with open(tmp_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="es",
            )
        texto = transcript.text.strip()
        logger.info(f"Transcripción: {texto}")
        return texto
    except Exception as e:
        logger.error(f"Error transcribiendo audio: {e}")
        raise
    finally:
        os.unlink(tmp_path)


def extraer_numero(texto: str) -> Optional[float]:
    """Extrae un número del texto hablado."""
    texto = texto.replace("$", "").replace("pesos", "").replace(".", "").replace(",", ".").strip()
    match = re.search(r"\d+(?:\.\d+)?", texto)
    if match:
        return float(match.group())
    return None


def extraer_cantidad(texto: str) -> Optional[float]:
    """Extrae cantidad numérica o palabras numéricas."""
    palabras = {
        "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4,
        "cinco": 5, "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10,
    }
    for palabra, valor in palabras.items():
        if palabra in texto.lower():
            return float(valor)
    return extraer_numero(texto)
