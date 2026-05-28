"""Integración con ARCA (ex-AFIP) - WSAA + WSFEv1"""
import os, json, base64, logging, subprocess, tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from zeep import Client
from zeep.helpers import serialize_object

logger = logging.getLogger(__name__)
HOMOLOGACION = os.environ.get("ARCA_HOMOLOGACION", "true").lower() == "true"
CUIT = 20295357909
PUNTO_VENTA = int(os.environ.get("ARCA_PUNTO_VENTA", "3"))

if HOMOLOGACION:
    WSAA_URL = "https://wsaahomo.afip.gov.ar/ws/services/LoginCms?wsdl"
    WSFE_URL = "https://wswhomo.afip.gov.ar/wsfev1/service.asmx?WSDL"
else:
    WSAA_URL = "https://wsaa.afip.gov.ar/ws/services/LoginCms?wsdl"
    WSFE_URL = "https://servicios1.afip.gov.ar/wsfev1/service.asmx?WSDL"

BASE_DIR = Path(__file__).parent
CERTS_DIR = BASE_DIR / "certs"; CERTS_DIR.mkdir(exist_ok=True)
CERT_PATH = CERTS_DIR / ("neuron-homo.crt" if HOMOLOGACION else "neuron-prod.crt")
KEY_PATH = CERTS_DIR / "neuron.key"
TOKEN_FILE = CERTS_DIR / "ta_cache.json"
SERVICE = "wsfe"

TIPO_FACTURA_A = 1; TIPO_FACTURA_B = 6
DOC_CUIT = 80; DOC_DNI = 96; DOC_CF = 99

def _ensure_certs():
    if not KEY_PATH.exists():
        kb = os.environ.get("ARCA_KEY_B64")
        if kb:
            with open(KEY_PATH,"wb") as f: f.write(base64.b64decode(kb))
        else:
            raise FileNotFoundError("Falta neuron.key / ARCA_KEY_B64")
    if not CERT_PATH.exists():
        ev = "ARCA_CERT_HOMO_B64" if HOMOLOGACION else "ARCA_CERT_PROD_B64"
        cb = os.environ.get(ev)
        if cb:
            with open(CERT_PATH,"wb") as f: f.write(base64.b64decode(cb))
        else:
            raise FileNotFoundError(f"Falta certificado / {ev}")

def _crear_tra():
    now = datetime.now(timezone.utc)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<loginTicketRequest version="1.0"><header>
<uniqueId>{int(now.timestamp())}</uniqueId>
<generationTime>{(now-timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%S-00:00")}</generationTime>
<expirationTime>{(now+timedelta(hours=12)).strftime("%Y-%m-%dT%H:%M:%S-00:00")}</expirationTime>
</header><service>{SERVICE}</service></loginTicketRequest>"""

def _obtener_token_nuevo():
    _ensure_certs()
    tra = _crear_tra()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
        f.write(tra); tra_path = f.name
    cms_path = tra_path.replace(".xml",".cms")
    try:
        subprocess.run(["openssl","smime","-sign","-in",tra_path,"-out",cms_path,
                        "-signer",str(CERT_PATH),"-inkey",str(KEY_PATH),"-outform","DER","-nodetach"],
                       check=True, capture_output=True)
        with open(cms_path,"rb") as f: cms_b64 = base64.b64encode(f.read()).decode()
    finally:
        os.unlink(tra_path)
        if os.path.exists(cms_path): os.unlink(cms_path)
    client = Client(WSAA_URL)
    response = client.service.loginCms(in0=cms_b64)
    import xml.etree.ElementTree as ET
    root = ET.fromstring(response)
    ta = {"token": root.find(".//token").text, "sign": root.find(".//sign").text,
          "expirationTime": root.find(".//expirationTime").text}
    with open(TOKEN_FILE,"w") as f: json.dump(ta,f)
    return ta

def _obtener_ta():
    if TOKEN_FILE.exists():
        with open(TOKEN_FILE) as f: ta = json.load(f)
        try:
            if datetime.fromisoformat(ta["expirationTime"]) > datetime.now(timezone.utc)+timedelta(minutes=5):
                return ta
        except Exception: pass
    return _obtener_token_nuevo()

def _auth():
    ta = _obtener_ta()
    return {"Token": ta["token"], "Sign": ta["sign"], "Cuit": CUIT}

def obtener_ultimo_numero(tipo_comp, pv=None):
    pv = pv or PUNTO_VENTA
    res = Client(WSFE_URL).service.FECompUltimoAutorizado(Auth=_auth(), PtoVta=pv, CbteTipo=tipo_comp)
    return int(res.CbteNro)

def emitir_factura(tipo, cliente_doc_tipo, cliente_doc_nro, items, concepto=1, punto_venta=None):
    pv = punto_venta or PUNTO_VENTA
    tipo_comp = TIPO_FACTURA_A if tipo == "A" else TIPO_FACTURA_B
    imp_neto = 0.0; imp_iva = 0.0; iva_por_ali = {}
    for it in items:
        qty = it["qty"]; ali = it.get("alicuota_iva", 21)
        if tipo == "A":
            neto = qty*it["precio"]; iva = neto*(ali/100)
        else:
            tot = qty*it["precio"]; neto = tot/(1+ali/100); iva = tot-neto
        imp_neto += neto; imp_iva += iva
        iva_por_ali.setdefault(ali, {"base":0,"importe":0})
        iva_por_ali[ali]["base"] += neto; iva_por_ali[ali]["importe"] += iva
    imp_neto = round(imp_neto,2); imp_iva = round(imp_iva,2); imp_total = round(imp_neto+imp_iva,2)
    ali_ids = {21:5, 10.5:4, 27:6, 5:8, 2.5:9, 0:3}
    iva_arr = [{"Id":ali_ids.get(a,5),"BaseImp":round(v["base"],2),"Importe":round(v["importe"],2)} for a,v in iva_por_ali.items()]
    nro = obtener_ultimo_numero(tipo_comp, pv) + 1
    fecha = datetime.now().strftime("%Y%m%d")
    req = {"FeCabReq":{"CantReg":1,"PtoVta":pv,"CbteTipo":tipo_comp},
           "FeDetReq":{"FECAEDetRequest":[{"Concepto":concepto,"DocTipo":cliente_doc_tipo,"DocNro":cliente_doc_nro,
           "CbteDesde":nro,"CbteHasta":nro,"CbteFch":fecha,"ImpTotal":imp_total,"ImpTotConc":0,"ImpNeto":imp_neto,
           "ImpOpEx":0,"ImpIVA":imp_iva,"ImpTrib":0,"MonId":"PES","MonCotiz":1,"Iva":{"AlicIva":iva_arr}}]}}
    res = Client(WSFE_URL).service.FECAESolicitar(Auth=_auth(), FeCAEReq=req)
    rd = serialize_object(res)
    det = rd["FeDetResp"]["FECAEDetResponse"][0]
    if det["Resultado"] != "A":
        raise Exception(f"RECHAZADA: {det.get('Observaciones')} {rd.get('Errors')}")
    return {"cae":det["CAE"], "vencimiento_cae":det["CAEFchVto"], "numero":nro, "punto_venta":pv,
            "tipo":tipo, "total":imp_total, "neto":imp_neto, "iva":imp_iva, "fecha":fecha}

def detectar_tipo_doc(doc):
    d = doc.replace("-","").replace(" ","").replace(".","")
    if not d or d == "-" or not d.isdigit(): return DOC_CF, 0
    if len(d) == 11: return DOC_CUIT, int(d)
    if len(d) in (7,8): return DOC_DNI, int(d)
    return DOC_CF, 0

def generar_qr_afip(cuit_emisor, fecha, pto_vta, tipo, nro, importe, doc_tipo, doc_nro, cae):
    import qrcode
    from io import BytesIO
    fi = f"{fecha[:4]}-{fecha[4:6]}-{fecha[6:8]}"
    data = {"ver":1,"fecha":fi,"cuit":cuit_emisor,"ptoVta":pto_vta,"tipoCmp":tipo,"nroCmp":nro,
            "importe":importe,"moneda":"PES","ctz":1,"tipoDocRec":doc_tipo,"nroDocRec":doc_nro,
            "tipoCodAut":"E","codAut":int(cae)}
    b64 = base64.urlsafe_b64encode(json.dumps(data,separators=(",",":")).encode()).decode().rstrip("=")
    img = qrcode.make(f"https://www.afip.gob.ar/fe/qr/?p={b64}")
    buf = BytesIO(); img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()
