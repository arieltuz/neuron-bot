"""
Generador de PDFs - Neuron Computación
Presupuestos y Comprobantes X
"""

import io
from datetime import datetime, timedelta
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle,
    Paragraph, Spacer, Image as RLImage, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT

# ── Rutas ─────────────────────────────────────────────────────────────────────
BASE_DIR  = Path(__file__).parent
LOGO_PATH = BASE_DIR / "logo_neuron.png"

# ── Datos del local ───────────────────────────────────────────────────────────
LOCAL = {
    "nombre":    "Neuron Computación",
    "titular":   "Matías H. Carabajal",
    "cuit":      "20-29535790-9",
    "iva":       "IVA Responsable Inscripto",
    "tel":       "3731444804",
    "email":     "neuroncomputacion@gmail.com",
    "direccion": "Mariano Moreno 463",
}

# ── Paleta ────────────────────────────────────────────────────────────────────
DARK  = colors.HexColor("#2d2d2d")
BLUE  = colors.HexColor("#1a6fbf")
LGRAY = colors.HexColor("#f5f5f5")
MGRAY = colors.HexColor("#cccccc")

# ── Estilos comunes ───────────────────────────────────────────────────────────
def _styles():
    return {
        "label":   ParagraphStyle("label",  fontSize=8,  textColor=colors.grey,   fontName="Helvetica"),
        "value":   ParagraphStyle("value",  fontSize=9,  textColor=DARK,          fontName="Helvetica-Bold"),
        "normal":  ParagraphStyle("normal", fontSize=9,  textColor=DARK,          fontName="Helvetica"),
        "sub":     ParagraphStyle("sub",    fontSize=8,  textColor=colors.grey,   fontName="Helvetica"),
        "section": ParagraphStyle("sec",    fontSize=10, textColor=BLUE,          fontName="Helvetica-Bold"),
        "th":      ParagraphStyle("th",     fontSize=9,  textColor=colors.white,  fontName="Helvetica-Bold"),
        "th_r":    ParagraphStyle("th_r",   fontSize=9,  textColor=colors.white,  fontName="Helvetica-Bold", alignment=TA_RIGHT),
        "th_c":    ParagraphStyle("th_c",   fontSize=9,  textColor=colors.white,  fontName="Helvetica-Bold", alignment=TA_CENTER),
        "total":   ParagraphStyle("tot",    fontSize=12, textColor=BLUE,          fontName="Helvetica-Bold"),
        "total_r": ParagraphStyle("tot_r",  fontSize=12, textColor=BLUE,          fontName="Helvetica-Bold", alignment=TA_RIGHT),
        "footer":  ParagraphStyle("footer", fontSize=7,  textColor=colors.grey,   fontName="Helvetica",      alignment=TA_CENTER),
        "doctitle":ParagraphStyle("dt",     fontSize=22, textColor=BLUE,          fontName="Helvetica-Bold", alignment=TA_CENTER),
        "badge":   ParagraphStyle("badge",  fontSize=10, textColor=colors.white,  fontName="Helvetica-Bold", alignment=TA_CENTER),
    }

def fmt_pesos(v: float) -> str:
    return f"$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def _header(s: dict) -> Table:
    """Encabezado con logo + datos del local."""
    logo = RLImage(str(LOGO_PATH), width=7*cm, height=1.32*cm)
    info = [
        Paragraph(f"<b>{LOCAL['nombre']}</b>",
                  ParagraphStyle("lh", fontSize=11, textColor=DARK, fontName="Helvetica-Bold", alignment=TA_RIGHT)),
        Paragraph(LOCAL["direccion"],
                  ParagraphStyle("ls", fontSize=8, textColor=colors.grey, fontName="Helvetica", alignment=TA_RIGHT)),
        Paragraph(f"CUIT: {LOCAL['cuit']} | {LOCAL['iva']}",
                  ParagraphStyle("ls", fontSize=8, textColor=colors.grey, fontName="Helvetica", alignment=TA_RIGHT)),
        Paragraph(f"Tel: {LOCAL['tel']} | {LOCAL['email']}",
                  ParagraphStyle("ls", fontSize=8, textColor=colors.grey, fontName="Helvetica", alignment=TA_RIGHT)),
        Paragraph(LOCAL["titular"],
                  ParagraphStyle("ls", fontSize=8, textColor=colors.grey, fontName="Helvetica", alignment=TA_RIGHT)),
    ]
    t = Table([[logo, info]], colWidths=[8*cm, 10.5*cm])
    t.setStyle(TableStyle([
        ("VALIGN",  (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN",   (0, 0), (0, 0),   "LEFT"),
        ("ALIGN",   (1, 0), (1, 0),   "RIGHT"),
    ]))
    return t

def _tabla_items(items: list, s: dict) -> Table:
    """Tabla de ítems compartida."""
    rows = [[
        Paragraph("Cant.",       s["th_c"]),
        Paragraph("Descripción", s["th"]),
        Paragraph("P. Unit.",    s["th_r"]),
        Paragraph("Subtotal",    s["th_r"]),
    ]]
    for it in items:
        sub = it["qty"] * it["precio"]
        qty_str = str(int(it["qty"])) if it["qty"] == int(it["qty"]) else str(it["qty"])
        rows.append([
            Paragraph(qty_str,             ParagraphStyle("c", fontSize=9, fontName="Helvetica", alignment=TA_CENTER)),
            Paragraph(it["desc"],          ParagraphStyle("n", fontSize=9, fontName="Helvetica")),
            Paragraph(fmt_pesos(it["precio"]), ParagraphStyle("r", fontSize=9, fontName="Helvetica", alignment=TA_RIGHT)),
            Paragraph(fmt_pesos(sub),          ParagraphStyle("r", fontSize=9, fontName="Helvetica", alignment=TA_RIGHT)),
        ])

    t = Table(rows, colWidths=[1.5*cm, 11*cm, 3.2*cm, 2.8*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, 0),  DARK),
        ("ROWBACKGROUNDS",(0, 1),(-1, -1), [colors.white, LGRAY]),
        ("GRID",         (0, 0), (-1, -1), 0.3, MGRAY),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",   (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 5),
    ]))
    return t

def _tabla_datos_cliente(s: dict, **kv) -> Table:
    """Tabla de 2 columnas para datos del cliente."""
    rows = []
    items_kv = list(kv.items())
    for i in range(0, len(items_kv), 2):
        row = []
        for j in range(2):
            if i + j < len(items_kv):
                k, v = items_kv[i + j]
                row += [Paragraph(f"{k}:", s["label"]), Paragraph(v or "-", s["value"])]
            else:
                row += ["", ""]
        rows.append(row)
    t = Table(rows, colWidths=[3.2*cm, 5.3*cm, 3.2*cm, 6.8*cm])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING",(0,0),(-1,-1),3)]))
    return t

# ══════════════════════════════════════════════════════════════════════════════
# PRESUPUESTO
# ══════════════════════════════════════════════════════════════════════════════
def generar_presupuesto_pdf(
    numero: str,
    cliente_nombre: str,
    cliente_dni: str,
    cliente_tel: str,
    items: list,
    notas: str = "",
) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
        leftMargin=1.5*cm, rightMargin=1.5*cm,
        topMargin=1.5*cm,  bottomMargin=1.5*cm)

    s     = _styles()
    story = []
    hoy   = datetime.now()
    valid = hoy + timedelta(days=7)

    # Header
    story.append(_header(s))
    story.append(HRFlowable(width="100%", thickness=2, color=BLUE, spaceAfter=6))

    # Título + número
    story.append(Paragraph("PRESUPUESTO", s["doctitle"]))
    story.append(Spacer(1, 0.3*cm))

    meta = Table([[
        Paragraph("N° Presupuesto:", s["label"]),
        Paragraph(numero, s["value"]),
        Paragraph("Fecha:", s["label"]),
        Paragraph(hoy.strftime("%d/%m/%Y"), s["value"]),
        Paragraph("Válido hasta:", s["label"]),
        Paragraph(valid.strftime("%d/%m/%Y"), s["value"]),
    ]], colWidths=[3*cm, 2.5*cm, 2*cm, 2.5*cm, 2.5*cm, 4*cm])
    meta.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"MIDDLE")]))
    story.append(meta)
    story.append(Spacer(1, 0.4*cm))

    # Datos cliente
    story.append(HRFlowable(width="100%", thickness=0.5, color=MGRAY, spaceAfter=4))
    story.append(Paragraph("DATOS DEL CLIENTE", s["section"]))
    story.append(Spacer(1, 0.2*cm))
    story.append(_tabla_datos_cliente(s,
        Nombre=cliente_nombre,
        **{"DNI/CUIT": cliente_dni},
        Teléfono=cliente_tel,
    ))
    story.append(Spacer(1, 0.4*cm))

    # Ítems
    story.append(HRFlowable(width="100%", thickness=0.5, color=MGRAY, spaceAfter=4))
    story.append(Paragraph("DETALLE", s["section"]))
    story.append(Spacer(1, 0.2*cm))
    story.append(_tabla_items(items, s))
    story.append(Spacer(1, 0.3*cm))

    # Totales
    subtotal = sum(it["qty"] * it["precio"] for it in items)
    iva      = subtotal * 0.21
    total    = subtotal + iva

    totales = [
        ["", "", Paragraph("Subtotal:", s["label"]),  Paragraph(fmt_pesos(subtotal), s["value"])],
        ["", "", Paragraph("IVA (21%):", s["label"]), Paragraph(fmt_pesos(iva),      s["value"])],
        ["", "", Paragraph("TOTAL:",     s["total"]),  Paragraph(fmt_pesos(total),    s["total_r"])],
    ]
    tot = Table(totales, colWidths=[1.5*cm, 11*cm, 3.2*cm, 2.8*cm])
    tot.setStyle(TableStyle([
        ("ALIGN",      (2, 0), (3, -1), "RIGHT"),
        ("LINEABOVE",  (2, 2), (3, 2),  1, BLUE),
        ("TOPPADDING", (0, 0), (-1,-1), 3),
    ]))
    story.append(tot)
    story.append(Spacer(1, 0.4*cm))

    # Notas
    if notas and notas != "-":
        story.append(HRFlowable(width="100%", thickness=0.5, color=MGRAY, spaceAfter=4))
        story.append(Paragraph("Observaciones:", s["label"]))
        story.append(Paragraph(notas, s["normal"]))
        story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph(
        "Precios sujetos a cambio sin previo aviso. Validez del presupuesto: 7 días.",
        ParagraphStyle("disc", fontSize=8, textColor=colors.grey, fontName="Helvetica-Oblique")
    ))

    # Pie
    story.append(Spacer(1, 1*cm))
    story.append(HRFlowable(width="100%", thickness=1, color=BLUE, spaceAfter=4))
    story.append(Paragraph(
        f"{LOCAL['nombre']} | {LOCAL['direccion']} | Tel: {LOCAL['tel']} | {LOCAL['email']}",
        s["footer"]
    ))

    doc.build(story)
    buf.seek(0)
    return buf.getvalue()

# ══════════════════════════════════════════════════════════════════════════════
# COMPROBANTE X
# ══════════════════════════════════════════════════════════════════════════════
def generar_comprobante_x_pdf(
    numero: str,
    cliente_nombre: str,
    cliente_cuit: str,
    cliente_tel: str,
    items: list,
    notas: str = "",
) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
        leftMargin=1.5*cm, rightMargin=1.5*cm,
        topMargin=1.5*cm,  bottomMargin=1.5*cm)

    s     = _styles()
    story = []
    hoy   = datetime.now()

    # Header
    story.append(_header(s))
    story.append(HRFlowable(width="100%", thickness=2, color=BLUE, spaceAfter=6))

    # Badge COMPROBANTE X
    badge_data = [[Paragraph("COMPROBANTE X", s["badge"])]]
    badge = Table(badge_data, colWidths=[18.5*cm])
    badge.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(0,0), DARK),
        ("TOPPADDING",    (0,0),(0,0), 8),
        ("BOTTOMPADDING", (0,0),(0,0), 8),
        ("ROUNDEDCORNERS",(0,0),(0,0), [4,4,4,4]),
    ]))
    story.append(badge)
    story.append(Spacer(1, 0.4*cm))

    # Meta
    meta = Table([[
        Paragraph("N° Comprobante:", s["label"]),
        Paragraph(numero, s["value"]),
        Paragraph("Fecha:", s["label"]),
        Paragraph(hoy.strftime("%d/%m/%Y"), s["value"]),
        Paragraph("Hora:", s["label"]),
        Paragraph(hoy.strftime("%H:%M"), s["value"]),
    ]], colWidths=[3.5*cm, 2.5*cm, 2*cm, 2.5*cm, 2*cm, 4*cm])
    meta.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"MIDDLE")]))
    story.append(meta)
    story.append(Spacer(1, 0.4*cm))

    # Emisor
    story.append(HRFlowable(width="100%", thickness=0.5, color=MGRAY, spaceAfter=4))
    story.append(Paragraph("EMISOR", s["section"]))
    story.append(Spacer(1, 0.2*cm))
    story.append(_tabla_datos_cliente(s,
        Razón=LOCAL["nombre"],
        CUIT=LOCAL["cuit"],
        **{"Cond. IVA": LOCAL["iva"]},
        Dirección=LOCAL["direccion"],
    ))
    story.append(Spacer(1, 0.4*cm))

    # Receptor
    story.append(HRFlowable(width="100%", thickness=0.5, color=MGRAY, spaceAfter=4))
    story.append(Paragraph("RECEPTOR", s["section"]))
    story.append(Spacer(1, 0.2*cm))
    story.append(_tabla_datos_cliente(s,
        Nombre=cliente_nombre,
        CUIT=cliente_cuit,
        Teléfono=cliente_tel,
    ))
    story.append(Spacer(1, 0.4*cm))

    # Ítems
    story.append(HRFlowable(width="100%", thickness=0.5, color=MGRAY, spaceAfter=4))
    story.append(Paragraph("DETALLE", s["section"]))
    story.append(Spacer(1, 0.2*cm))
    story.append(_tabla_items(items, s))
    story.append(Spacer(1, 0.3*cm))

    # Total (Comprobante X no discrimina IVA)
    total = sum(it["qty"] * it["precio"] for it in items)
    tot_rows = [
        ["", "", Paragraph("TOTAL:", s["total"]), Paragraph(fmt_pesos(total), s["total_r"])],
    ]
    tot = Table(tot_rows, colWidths=[1.5*cm, 11*cm, 3.2*cm, 2.8*cm])
    tot.setStyle(TableStyle([
        ("ALIGN",      (2,0),(3,-1), "RIGHT"),
        ("LINEABOVE",  (2,0),(3,0),  1, BLUE),
        ("TOPPADDING", (0,0),(-1,-1), 4),
    ]))
    story.append(tot)
    story.append(Spacer(1, 0.4*cm))

    # Notas
    if notas and notas != "-":
        story.append(HRFlowable(width="100%", thickness=0.5, color=MGRAY, spaceAfter=4))
        story.append(Paragraph("Observaciones:", s["label"]))
        story.append(Paragraph(notas, s["normal"]))
        story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph(
        "Este comprobante no tiene validez fiscal como factura electrónica.",
        ParagraphStyle("disc", fontSize=8, textColor=colors.grey, fontName="Helvetica-Oblique")
    ))

    # Firma
    story.append(Spacer(1, 1.5*cm))
    firma = Table([[
        "",
        Table(
            [[Paragraph("_" * 30, s["normal"])],
             [Paragraph(LOCAL["titular"], ParagraphStyle("fc", fontSize=9, alignment=TA_CENTER, fontName="Helvetica"))]],
            colWidths=[6*cm]
        )
    ]], colWidths=[12.5*cm, 6*cm])
    story.append(firma)

    # Pie
    story.append(Spacer(1, 0.8*cm))
    story.append(HRFlowable(width="100%", thickness=1, color=BLUE, spaceAfter=4))
    story.append(Paragraph(
        f"{LOCAL['nombre']} | {LOCAL['direccion']} | Tel: {LOCAL['tel']} | {LOCAL['email']}",
        s["footer"]
    ))

    doc.build(story)
    buf.seek(0)
    return buf.getvalue()
