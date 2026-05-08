"""
Reconocimiento de voz con Whisper API via requests (sin librería openai)
"""

import os
import re
import logging
import tempfile
import requests
from typing import Optional

logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.environ.get(
    "OPENAI_API_KEY",
    "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"
)


async def transcribir_audio(file_bytes: bytes, extension: str = "ogg") -> str:
    """Transcribe audio con Whisper API usando requests directamente."""
    with tempfile.NamedTemporaryFile(suffix=f".{extension}", delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    try:
        with open(tmp_path, "rb") as audio_file:
            response = requests.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                files={"file": (f"audio.{extension}", audio_file, "audio/ogg")},
                data={"model": "whisper-1", "language": "es"},
                timeout=30,
            )
        response.raise_for_status()
        texto = response.json().get("text", "").strip()
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
