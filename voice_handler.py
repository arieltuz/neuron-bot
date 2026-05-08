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
    logger.info(f"Iniciando transcripción - bytes: {len(file_bytes)}, ext: {extension}")
    logger.info(f"API key presente: {bool(OPENAI_API_KEY)}, primeros 10 chars: {OPENAI_API_KEY[:10] if OPENAI_API_KEY else 'NONE'}")

    with tempfile.NamedTemporaryFile(suffix=f".{extension}", delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name
        logger.info(f"Audio guardado en: {tmp_path}")

    try:
        with open(tmp_path, "rb") as audio_file:
            logger.info("Enviando request a OpenAI...")
            response = requests.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                files={"file": (f"audio.{extension}", audio_file, "audio/ogg")},
                data={"model": "whisper-1", "language": "es"},
                timeout=60,
            )
        logger.info(f"Respuesta OpenAI - status: {response.status_code}")
        logger.info(f"Respuesta body: {response.text[:500]}")

        if response.status_code != 200:
            error_msg = f"Error OpenAI {response.status_code}: {response.text}"
            logger.error(error_msg)
            raise Exception(error_msg)

        texto = response.json().get("text", "").strip()
        logger.info(f"Transcripción exitosa: {texto}")
        return texto
    except Exception as e:
        logger.error(f"Error transcribiendo audio: {type(e).__name__}: {e}")
        raise
    finally:
        try:
            os.unlink(tmp_path)
        except:
            pass


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
