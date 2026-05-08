"""
Módulo de reconocimiento de voz con OpenAI Whisper
Para el bot de Neuron Computación
"""

import os
import io
import re
import logging
import tempfile

from openai import OpenAI

logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "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")

client = OpenAI(api_key=OPENAI_API_KEY)


async def transcribir_audio(file_bytes: bytes, extension: str = "ogg") -> str:
    """
    Transcribe un audio usando Whisper de OpenAI.
    Retorna el texto transcripto en español.
    """
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


def interpretar_intencion(texto: str) -> dict:
    """
    Analiza el texto transcripto e intenta extraer:
    - tipo: 'presupuesto' | 'comprobante' | None
    - datos extraídos directamente del mensaje (opcional)
    """
    texto_lower = texto.lower()
    resultado = {"tipo": None, "texto_original": texto}

    # Detectar tipo de documento
    if any(p in texto_lower for p in ["presupuesto", "presupu", "cotización", "cotizacion", "precio"]):
        resultado["tipo"] = "presupuesto"
    elif any(p in texto_lower for p in ["comprobante", "factura", "recibo", "ticket", "venta"]):
        resultado["tipo"] = "comprobante"

    return resultado


def extraer_numero(texto: str) -> float | None:
    """Intenta extraer un número del texto hablado."""
    # Limpiar símbolos
    texto = texto.replace("$", "").replace("pesos", "").replace(".", "").replace(",", ".").strip()
    # Buscar número
    match = re.search(r"\d+(?:\.\d+)?", texto)
    if match:
        return float(match.group())
    return None


def extraer_cantidad(texto: str) -> float | None:
    """Extrae cantidad numérica o palabras numéricas simples."""
    palabras = {
        "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4,
        "cinco": 5, "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10,
    }
    texto_lower = texto.lower().strip()
    for palabra, valor in palabras.items():
        if palabra in texto_lower:
            return float(valor)
    return extraer_numero(texto)
