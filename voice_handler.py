"""Reconocimiento de voz con Vosk (gratis, offline)"""
import os, re, json, logging, tempfile, subprocess, urllib.request, zipfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)
MODEL_NAME = "vosk-model-small-es-0.42"
MODEL_URL = f"https://alphacephei.com/vosk/models/{MODEL_NAME}.zip"
MODEL_DIR = Path(__file__).parent / "models"
MODEL_PATH = MODEL_DIR / MODEL_NAME
_model = None

def _descargar_modelo():
    if MODEL_PATH.exists(): return
    logger.info("📥 Descargando modelo Vosk español (~40MB)...")
    MODEL_DIR.mkdir(exist_ok=True)
    zip_path = MODEL_DIR / f"{MODEL_NAME}.zip"
    urllib.request.urlretrieve(MODEL_URL, zip_path)
    with zipfile.ZipFile(zip_path, "r") as z: z.extractall(MODEL_DIR)
    zip_path.unlink()
    logger.info("✅ Modelo Vosk listo.")

def _cargar_modelo():
    global _model
    if _model is None:
        from vosk import Model, SetLogLevel
        SetLogLevel(-1)
        _descargar_modelo()
        _model = Model(str(MODEL_PATH))
        logger.info("✅ Modelo Vosk cargado.")
    return _model

def _convertir_a_wav(inp, out):
    subprocess.run(["ffmpeg","-y","-i",inp,"-ar","16000","-ac","1","-f","wav",out], check=True, capture_output=True)

async def transcribir_audio(file_bytes: bytes, extension: str = "ogg") -> str:
    from vosk import KaldiRecognizer
    import wave
    with tempfile.NamedTemporaryFile(suffix=f".{extension}", delete=False) as t:
        t.write(file_bytes); tmp_in = t.name
    tmp_wav = tmp_in.replace(f".{extension}", ".wav")
    try:
        _convertir_a_wav(tmp_in, tmp_wav)
        model = _cargar_modelo()
        with wave.open(tmp_wav, "rb") as wf:
            rec = KaldiRecognizer(model, wf.getframerate()); rec.SetWords(False)
            res = []
            while True:
                data = wf.readframes(4000)
                if len(data) == 0: break
                if rec.AcceptWaveform(data):
                    r = json.loads(rec.Result())
                    if r.get("text"): res.append(r["text"])
            rf = json.loads(rec.FinalResult())
            if rf.get("text"): res.append(rf["text"])
        texto = " ".join(res).strip()
        logger.info(f"Transcripción: {texto}")
        return texto
    finally:
        for p in (tmp_in, tmp_wav):
            try: os.unlink(p)
            except Exception: pass

def extraer_numero(texto: str) -> Optional[float]:
    t = texto.replace("$","").replace("pesos","").replace(".","").replace(",",".").strip()
    m = re.search(r"\d+(?:\.\d+)?", t)
    if m: return float(m.group())
    nums = {"cero":0,"uno":1,"una":1,"dos":2,"tres":3,"cuatro":4,"cinco":5,"seis":6,"siete":7,"ocho":8,"nueve":9,"diez":10,
            "once":11,"doce":12,"trece":13,"catorce":14,"quince":15,"veinte":20,"treinta":30,"cuarenta":40,"cincuenta":50,
            "sesenta":60,"setenta":70,"ochenta":80,"noventa":90,"cien":100,"ciento":100,"doscientos":200,"trescientos":300,
            "cuatrocientos":400,"quinientos":500,"seiscientos":600,"setecientos":700,"ochocientos":800,"novecientos":900,"mil":1000}
    palabras = t.lower().split(); total=0; actual=0; found=False
    for p in palabras:
        if p in nums:
            found=True; v=nums[p]
            if v==1000: actual=(actual or 1)*1000; total+=actual; actual=0
            elif v>=100: actual=(actual or 1)*v
            else: actual+=v
    total+=actual
    return float(total) if found and total>0 else None

def extraer_cantidad(texto: str) -> Optional[float]:
    p = {"uno":1,"una":1,"dos":2,"tres":3,"cuatro":4,"cinco":5,"seis":6,"siete":7,"ocho":8,"nueve":9,"diez":10}
    for k,v in p.items():
        if k in texto.lower().split(): return float(v)
    return extraer_numero(texto)
