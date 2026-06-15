"""
Bot de Telegram - Neuron Computación
Presupuestos, Comprobantes X, Facturas A/B (ARCA) y conversión de presupuestos.
Soporta comandos de voz en español via Vosk.
"""

import os
import io
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ConversationHandler, ContextTypes, filters
)

from pdf_generator import generar_presupuesto_pdf, generar_comprobante_x_pdf
from voice_handler import transcribir_audio, extraer_numero, extraer_cantidad
import db

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("TELEGRAM_TOKEN", "8362308263:AAGA2gxYn-qCjtxO9rbOhBvTPELl8Yu52ro")

(
    MENU_PRINCIPAL,
    PRES_CLIENTE_NOMBRE, PRES_CLIENTE_DNI, PRES_CLIENTE_TEL,
    PRES_ITEM_DESC, PRES_ITEM_QTY, PRES_ITEM_PRECIO,
    PRES_MAS_ITEMS, PRES_NOTAS, PRES_CONFIRMAR,
    COMP_CLIENTE_NOMBRE, COMP_CLIENTE_CUIT, COMP_CLIENTE_TEL,
    COMP_ITEM_DESC, COMP_ITEM_QTY, COMP_ITEM_PRECIO,
    COMP_MAS_ITEMS, COMP_NOTAS, COMP_CONFIRMAR,
    FAC_TIPO, FAC_CLIENTE_NOMBRE, FAC_CLIENTE_DOC,
    FAC_ITEM_DESC, FAC_ITEM_QTY, FAC_ITEM_PRECIO, FAC_ITEM_IVA,
    FAC_MAS_ITEMS, FAC_CONFIRMAR,
    CONV_NUMERO, CONV_TIPO,
) = range(30)

BASE_DIR = Path(__file__).parent

def next_number(tipo):
    return db.next_number(tipo)

def _guardar_presupuesto(numero: str, datos: dict):
    db.guardar_presupuesto(numero, datos)

def _buscar_presupuesto(numero: str):
    return db.buscar_presupuesto(numero)

def fmt_pesos(v):
    return f"$ {v:,.2f}".replace(",","X").replace(".",",").replace("X",".")

def teclado_si_no():
    return ReplyKeyboardMarkup([["✅ Sí","❌ No"]], resize_keyboard=True, one_time_keyboard=True)

def teclado_menu():
    return ReplyKeyboardMarkup([["📄 Presupuesto","🧾 Comprobante X"],["🧾 Factura A/B","❓ Ayuda"]], resize_keyboard=True)

def teclado_factura_tipo():
    return ReplyKeyboardMarkup([["🅰️ Factura A","🅱️ Factura B"],["❌ Cancelar"]], resize_keyboard=True, one_time_keyboard=True)

def teclado_iva():
    return ReplyKeyboardMarkup([["21%","10.5%"]], resize_keyboard=True, one_time_keyboard=True)

def teclado_conv_tipo():
    return ReplyKeyboardMarkup([["🧾 Comprobante X"],["🅰️ Factura A","🅱️ Factura B"],["❌ Cancelar"]], resize_keyboard=True, one_time_keyboard=True)

async def get_texto(update: Update):
    msg = update.message
    if msg.voice or msg.audio:
        obj = msg.voice or msg.audio
        await msg.reply_text("🎙️ Transcribiendo tu mensaje de voz...")
        try:
            file = await obj.get_file()
            file_bytes = await file.download_as_bytearray()
            texto = await transcribir_audio(bytes(file_bytes), "ogg")
            await msg.reply_text(f"📝 Escuché: _{texto}_", parse_mode="Markdown")
            return texto
        except Exception as e:
            logger.error(f"Error transcripción: {e}")
            await msg.reply_text("⚠️ No pude entender el audio. Intentá de nuevo o escribí el texto.")
            return None
    return msg.text.strip() if msg.text else None

# ══════════════════════════════════════════════════════════════════════════════
# Menú
# ══════════════════════════════════════════════════════════════════════════════
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 ¡Hola! Soy el bot de *Neuron Computación*.\n\n"
        "Podés escribirme o mandarme un 🎙️ *mensaje de voz*.\n\n¿Qué querés generar?",
        parse_mode="Markdown", reply_markup=teclado_menu())
    return MENU_PRINCIPAL

async def ayuda(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📋 *Comandos:*\n"
        "/start - Menú principal\n"
        "/presupuesto - Nuevo presupuesto\n"
        "/comprobante - Nuevo Comprobante X\n"
        "/factura - Nueva Factura A/B\n"
        "/convertir <número> - Convierte un presupuesto en comprobante/factura\n"
        "   _(ej: /convertir 0005)_\n"
        "/cancelar - Cancela operación actual\n\n"
        "🎙️ También podés hablar en cualquier paso.",
        parse_mode="Markdown", reply_markup=teclado_menu())
    return MENU_PRINCIPAL

async def cancelar(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.clear()
    await update.message.reply_text("❌ Operación cancelada.", reply_markup=teclado_menu())
    return ConversationHandler.END

async def menu_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    texto = await get_texto(update)
    if not texto: return MENU_PRINCIPAL
    tl = texto.lower()
    if any(p in tl for p in ["presupuesto","presupu","cotiz","precio"]):
        return await iniciar_presupuesto(update, ctx)
    elif "factura" in tl:
        return await iniciar_factura(update, ctx)
    elif any(p in tl for p in ["comprobante","recibo","ticket","compro"]):
        return await iniciar_comprobante(update, ctx)
    elif any(p in tl for p in ["ayuda","help","?"]):
        return await ayuda(update, ctx)
    else:
        await update.message.reply_text(
            "No entendí 😅 Usá los botones o escribí *presupuesto*, *comprobante* o *factura* 👇",
            parse_mode="Markdown", reply_markup=teclado_menu())
        return MENU_PRINCIPAL

# ══════════════════════════════════════════════════════════════════════════════
# PRESUPUESTO
# ══════════════════════════════════════════════════════════════════════════════
async def iniciar_presupuesto(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.clear(); ctx.user_data["items"] = []
    await update.message.reply_text(
        "📄 *Nuevo Presupuesto*\n\nPaso 1/3 — Datos del cliente\n\n"
        "✏️ *Nombre completo* del cliente:\n_(escribí o mandá un audio — decí `-` para omitir)_",
        parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())
    return PRES_CLIENTE_NOMBRE

async def pres_cliente_nombre(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    texto = await get_texto(update)
    if not texto: return PRES_CLIENTE_NOMBRE
    ctx.user_data["cliente_nombre"] = texto
    await update.message.reply_text("✏️ *DNI o CUIT* del cliente:", parse_mode="Markdown")
    return PRES_CLIENTE_DNI

async def pres_cliente_dni(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    texto = await get_texto(update)
    if not texto: return PRES_CLIENTE_DNI
    ctx.user_data["cliente_dni"] = texto
    await update.message.reply_text("✏️ *Teléfono* del cliente:", parse_mode="Markdown")
    return PRES_CLIENTE_TEL

async def pres_cliente_tel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    texto = await get_texto(update)
    if not texto: return PRES_CLIENTE_TEL
    ctx.user_data["cliente_tel"] = texto
    await update.message.reply_text(
        "✅ Datos guardados.\n\n📦 Paso 2/3 — Ítems\n\n✏️ *Descripción* del ítem:",
        parse_mode="Markdown")
    return PRES_ITEM_DESC

async def pres_item_desc(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    texto = await get_texto(update)
    if not texto: return PRES_ITEM_DESC
    ctx.user_data["_item_desc"] = texto
    await update.message.reply_text("✏️ *Cantidad*:", parse_mode="Markdown")
    return PRES_ITEM_QTY

async def pres_item_qty(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    texto = await get_texto(update)
    if not texto: return PRES_ITEM_QTY
    qty = extraer_cantidad(texto)
    if qty is None:
        await update.message.reply_text("⚠️ No entendí la cantidad. Intentá de nuevo:")
        return PRES_ITEM_QTY
    ctx.user_data["_item_qty"] = qty
    await update.message.reply_text("✏️ *Precio unitario* (sin $):", parse_mode="Markdown")
    return PRES_ITEM_PRECIO

async def pres_item_precio(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    texto = await get_texto(update)
    if not texto: return PRES_ITEM_PRECIO
    precio = extraer_numero(texto)
    if precio is None:
        await update.message.reply_text("⚠️ No entendí el precio. Intentá de nuevo:")
        return PRES_ITEM_PRECIO
    qty = ctx.user_data.pop("_item_qty"); desc = ctx.user_data.pop("_item_desc")
    ctx.user_data["items"].append({"desc": desc, "qty": qty, "precio": precio})
    resumen = "\n".join(f"  • {it['qty']}x {it['desc']} — {fmt_pesos(it['precio'])}" for it in ctx.user_data["items"])
    await update.message.reply_text(
        f"✅ Ítem agregado.\n\n*Ítems:*\n{resumen}\n\n¿Agregar otro ítem?",
        parse_mode="Markdown", reply_markup=teclado_si_no())
    return PRES_MAS_ITEMS

async def pres_mas_items(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    texto = await get_texto(update)
    if not texto: return PRES_MAS_ITEMS
    if any(p in texto.lower() for p in ["sí","si","dale","otro","más","mas","quiero","yes"]):
        await update.message.reply_text("✏️ Descripción del siguiente ítem:", reply_markup=ReplyKeyboardRemove())
        return PRES_ITEM_DESC
    await update.message.reply_text(
        "📝 Paso 3/3 — ¿Alguna *observación*?\n_(o `-` para omitir)_",
        parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())
    return PRES_NOTAS

async def pres_notas(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    texto = await get_texto(update)
    if not texto: return PRES_NOTAS
    ctx.user_data["notas"] = texto
    items = ctx.user_data["items"]
    total = sum(it["qty"]*it["precio"] for it in items)
    detalle = "\n".join(f"  • {it['qty']}x {it['desc']} — {fmt_pesos(it['precio'])} c/u" for it in items)
    await update.message.reply_text(
        f"📄 *Resumen Presupuesto*\n\n"
        f"👤 {ctx.user_data.get('cliente_nombre','-')}\n"
        f"🪪 {ctx.user_data.get('cliente_dni','-')}\n"
        f"📞 {ctx.user_data.get('cliente_tel','-')}\n\n"
        f"*Ítems:*\n{detalle}\n\n*TOTAL: {fmt_pesos(total)}*\n\n"
        f"📝 {ctx.user_data.get('notas','-')}\n\n¿Confirmás y generás el PDF?",
        parse_mode="Markdown", reply_markup=teclado_si_no())
    return PRES_CONFIRMAR

async def pres_confirmar(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    texto = await get_texto(update)
    if not texto: return PRES_CONFIRMAR
    if any(p in texto.lower() for p in ["no","cancel"]):
        await update.message.reply_text("❌ Cancelado.", reply_markup=teclado_menu())
        ctx.user_data.clear(); return ConversationHandler.END
    numero = next_number("presupuesto")
    # Guardar presupuesto para poder convertirlo después
    _guardar_presupuesto(numero, {
        "cliente_nombre": ctx.user_data.get("cliente_nombre","-"),
        "cliente_dni":    ctx.user_data.get("cliente_dni","-"),
        "cliente_tel":    ctx.user_data.get("cliente_tel","-"),
        "items":          ctx.user_data["items"],
        "notas":          ctx.user_data.get("notas",""),
    })
    await update.message.reply_text("⏳ Generando PDF...", reply_markup=ReplyKeyboardRemove())
    pdf_bytes = generar_presupuesto_pdf(
        numero=numero, cliente_nombre=ctx.user_data.get("cliente_nombre","-"),
        cliente_dni=ctx.user_data.get("cliente_dni","-"), cliente_tel=ctx.user_data.get("cliente_tel","-"),
        items=ctx.user_data["items"], notas=ctx.user_data.get("notas",""))
    await update.message.reply_document(
        document=io.BytesIO(pdf_bytes), filename=f"Presupuesto_{numero}_NeuronComputacion.pdf",
        caption=f"✅ *Presupuesto N° {numero}* generado.\n\n"
                f"💡 Si el cliente lo aprueba, podés convertirlo con:\n`/convertir {numero}`",
        parse_mode="Markdown", reply_markup=teclado_menu())
    ctx.user_data.clear(); return ConversationHandler.END

# ══════════════════════════════════════════════════════════════════════════════
# COMPROBANTE X
# ══════════════════════════════════════════════════════════════════════════════
async def iniciar_comprobante(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.clear(); ctx.user_data["items"] = []
    await update.message.reply_text(
        "🧾 *Nuevo Comprobante X*\n\nPaso 1/3 — Datos del cliente\n\n✏️ *Nombre completo* del cliente:",
        parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())
    return COMP_CLIENTE_NOMBRE

async def comp_cliente_nombre(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    texto = await get_texto(update)
    if not texto: return COMP_CLIENTE_NOMBRE
    ctx.user_data["cliente_nombre"] = texto
    await update.message.reply_text("✏️ *CUIT* del cliente:", parse_mode="Markdown")
    return COMP_CLIENTE_CUIT

async def comp_cliente_cuit(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    texto = await get_texto(update)
    if not texto: return COMP_CLIENTE_CUIT
    ctx.user_data["cliente_cuit"] = texto
    await update.message.reply_text("✏️ *Teléfono* del cliente:", parse_mode="Markdown")
    return COMP_CLIENTE_TEL

async def comp_cliente_tel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    texto = await get_texto(update)
    if not texto: return COMP_CLIENTE_TEL
    ctx.user_data["cliente_tel"] = texto
    await update.message.reply_text(
        "✅ Datos guardados.\n\n📦 Paso 2/3 — Ítems\n\n✏️ *Descripción* del ítem:",
        parse_mode="Markdown")
    return COMP_ITEM_DESC

async def comp_item_desc(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    texto = await get_texto(update)
    if not texto: return COMP_ITEM_DESC
    ctx.user_data["_item_desc"] = texto
    await update.message.reply_text("✏️ *Cantidad*:", parse_mode="Markdown")
    return COMP_ITEM_QTY

async def comp_item_qty(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    texto = await get_texto(update)
    if not texto: return COMP_ITEM_QTY
    qty = extraer_cantidad(texto)
    if qty is None:
        await update.message.reply_text("⚠️ No entendí la cantidad. Intentá de nuevo:")
        return COMP_ITEM_QTY
    ctx.user_data["_item_qty"] = qty
    await update.message.reply_text("✏️ *Precio unitario* (sin $):", parse_mode="Markdown")
    return COMP_ITEM_PRECIO

async def comp_item_precio(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    texto = await get_texto(update)
    if not texto: return COMP_ITEM_PRECIO
    precio = extraer_numero(texto)
    if precio is None:
        await update.message.reply_text("⚠️ No entendí el precio. Intentá de nuevo:")
        return COMP_ITEM_PRECIO
    qty = ctx.user_data.pop("_item_qty"); desc = ctx.user_data.pop("_item_desc")
    ctx.user_data["items"].append({"desc": desc, "qty": qty, "precio": precio})
    resumen = "\n".join(f"  • {it['qty']}x {it['desc']} — {fmt_pesos(it['precio'])}" for it in ctx.user_data["items"])
    await update.message.reply_text(
        f"✅ Ítem agregado.\n\n*Ítems:*\n{resumen}\n\n¿Agregar otro ítem?",
        parse_mode="Markdown", reply_markup=teclado_si_no())
    return COMP_MAS_ITEMS

async def comp_mas_items(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    texto = await get_texto(update)
    if not texto: return COMP_MAS_ITEMS
    if any(p in texto.lower() for p in ["sí","si","dale","otro","más","mas","quiero","yes"]):
        await update.message.reply_text("✏️ Descripción del siguiente ítem:", reply_markup=ReplyKeyboardRemove())
        return COMP_ITEM_DESC
    await update.message.reply_text(
        "📝 Paso 3/3 — ¿Alguna *observación*?\n_(o `-` para omitir)_",
        parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())
    return COMP_NOTAS

async def comp_notas(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    texto = await get_texto(update)
    if not texto: return COMP_NOTAS
    ctx.user_data["notas"] = texto
    items = ctx.user_data["items"]
    total = sum(it["qty"]*it["precio"] for it in items)
    detalle = "\n".join(f"  • {it['qty']}x {it['desc']} — {fmt_pesos(it['precio'])} c/u" for it in items)
    await update.message.reply_text(
        f"🧾 *Resumen Comprobante X*\n\n"
        f"👤 {ctx.user_data.get('cliente_nombre','-')}\n"
        f"🪪 {ctx.user_data.get('cliente_cuit','-')}\n"
        f"📞 {ctx.user_data.get('cliente_tel','-')}\n\n"
        f"*Ítems:*\n{detalle}\n\n*TOTAL: {fmt_pesos(total)}*\n\n"
        f"📝 {ctx.user_data.get('notas','-')}\n\n¿Confirmás y generás el PDF?",
        parse_mode="Markdown", reply_markup=teclado_si_no())
    return COMP_CONFIRMAR

async def comp_confirmar(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    texto = await get_texto(update)
    if not texto: return COMP_CONFIRMAR
    if any(p in texto.lower() for p in ["no","cancel"]):
        await update.message.reply_text("❌ Cancelado.", reply_markup=teclado_menu())
        ctx.user_data.clear(); return ConversationHandler.END
    numero = next_number("comprobante")
    await update.message.reply_text("⏳ Generando PDF...", reply_markup=ReplyKeyboardRemove())
    pdf_bytes = generar_comprobante_x_pdf(
        numero=numero, cliente_nombre=ctx.user_data.get("cliente_nombre","-"),
        cliente_cuit=ctx.user_data.get("cliente_cuit","-"), cliente_tel=ctx.user_data.get("cliente_tel","-"),
        items=ctx.user_data["items"], notas=ctx.user_data.get("notas",""))
    await update.message.reply_document(
        document=io.BytesIO(pdf_bytes), filename=f"ComprobanteX_{numero}_NeuronComputacion.pdf",
        caption=f"✅ *Comprobante X N° {numero}* generado.", parse_mode="Markdown", reply_markup=teclado_menu())
    ctx.user_data.clear(); return ConversationHandler.END

# ══════════════════════════════════════════════════════════════════════════════
# CONVERTIR PRESUPUESTO
# ══════════════════════════════════════════════════════════════════════════════
async def convertir_presupuesto(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    # Puede venir con número: /convertir 0005
    args = ctx.args if hasattr(ctx, "args") else []
    if args:
        numero = args[0].strip().zfill(4)
        return await _mostrar_presupuesto(update, ctx, numero)
    await update.message.reply_text(
        "🔄 *Convertir Presupuesto*\n\n"
        "✏️ Escribí el *número* del presupuesto a convertir:\n_(ej: 0005)_",
        parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())
    return CONV_NUMERO

async def conv_numero(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    texto = await get_texto(update)
    if not texto: return CONV_NUMERO
    numero = texto.strip().zfill(4)
    return await _mostrar_presupuesto(update, ctx, numero)

async def _mostrar_presupuesto(update: Update, ctx: ContextTypes.DEFAULT_TYPE, numero: str):
    datos = _buscar_presupuesto(numero)
    if not datos:
        await update.message.reply_text(
            f"⚠️ No encontré el presupuesto N° {numero}.\n"
            "Verificá el número o generá uno nuevo.\n\n"
            "Escribí otro número o /cancelar.",
            reply_markup=ReplyKeyboardRemove())
        return CONV_NUMERO
    ctx.user_data["conv_datos"] = datos
    ctx.user_data["conv_numero"] = numero
    items = datos["items"]
    total = sum(it["qty"]*it["precio"] for it in items)
    detalle = "\n".join(f"  • {it['qty']}x {it['desc']} — {fmt_pesos(it['precio'])}" for it in items)
    await update.message.reply_text(
        f"📄 *Presupuesto N° {numero} encontrado:*\n\n"
        f"👤 {datos.get('cliente_nombre','-')}\n"
        f"🪪 {datos.get('cliente_dni','-')}\n\n"
        f"*Ítems:*\n{detalle}\n\n*TOTAL: {fmt_pesos(total)}*\n\n"
        "¿A qué lo querés convertir?",
        parse_mode="Markdown", reply_markup=teclado_conv_tipo())
    return CONV_TIPO

async def conv_tipo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    texto = await get_texto(update)
    if not texto: return CONV_TIPO
    if "cancel" in texto.lower():
        return await cancelar(update, ctx)

    datos = ctx.user_data["conv_datos"]
    numero_presupuesto = ctx.user_data["conv_numero"]

    # COMPROBANTE X — generar directamente sin pedir datos
    if "comprobante" in texto.lower() or "🧾 comprobante" in texto.lower():
        numero = next_number("comprobante")
        await update.message.reply_text("⏳ Generando Comprobante X...", reply_markup=ReplyKeyboardRemove())
        pdf_bytes = generar_comprobante_x_pdf(
            numero=numero,
            cliente_nombre=datos.get("cliente_nombre","-"),
            cliente_cuit=datos.get("cliente_dni","-"),
            cliente_tel=datos.get("cliente_tel","-"),
            items=datos["items"],
            notas=datos.get("notas",""))
        await update.message.reply_document(
            document=io.BytesIO(pdf_bytes),
            filename=f"ComprobanteX_{numero}_NeuronComputacion.pdf",
            caption=f"✅ *Comprobante X N° {numero}* generado a partir del Presupuesto N° {numero_presupuesto}.",
            parse_mode="Markdown", reply_markup=teclado_menu())
        ctx.user_data.clear()
        return ConversationHandler.END

    # FACTURA A/B — pre-cargar datos del presupuesto, saltar a resumen
    if "a" in texto.lower().replace("factura","").replace("🅰️","a")[:3] and "🅰" in texto or "factura a" in texto.lower():
        tipo_fac = "A"
    elif "🅱" in texto or "factura b" in texto.lower():
        tipo_fac = "B"
    else:
        tipo_fac = "B"

    from arca_handler import detectar_tipo_doc
    doc_tipo, doc_nro = detectar_tipo_doc(datos.get("cliente_dni", "-"))

    ctx.user_data.clear()
    ctx.user_data["items"] = datos["items"]
    ctx.user_data["fac_tipo"] = tipo_fac
    ctx.user_data["cliente_nombre"] = datos.get("cliente_nombre","-")
    ctx.user_data["cliente_doc_tipo"] = doc_tipo
    ctx.user_data["cliente_doc_nro"] = doc_nro
    ctx.user_data["conv_numero"] = numero_presupuesto

    for it in ctx.user_data["items"]:
        if "alicuota_iva" not in it:
            it["alicuota_iva"] = 21.0

    if tipo_fac == "A":
        cond = "IVA Responsable Inscripto"
    elif doc_tipo == 80:
        cond = "Monotributista / Exento"
    else:
        cond = "Consumidor Final"
    ctx.user_data["cliente_cond_iva"] = cond

    # Ir DIRECTAMENTE al resumen (sin pedir datos)
    return await _factura_resumen(update, ctx)

# ══════════════════════════════════════════════════════════════════════════════
# FACTURA ELECTRÓNICA (ARCA)
# ══════════════════════════════════════════════════════════════════════════════
async def iniciar_factura(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.clear(); ctx.user_data["items"] = []
    await update.message.reply_text(
        "🧾 *Nueva Factura Electrónica (ARCA)*\n\n¿Qué tipo querés emitir?\n\n"
        "• 🅰️ *Factura A* → clientes Responsables Inscriptos (con CUIT)\n"
        "• 🅱️ *Factura B* → Consumidores Finales, Monotributistas, Exentos",
        parse_mode="Markdown", reply_markup=teclado_factura_tipo())
    return FAC_TIPO

async def fac_tipo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    texto = await get_texto(update)
    if not texto: return FAC_TIPO
    if "cancel" in texto.lower():
        return await cancelar(update, ctx)
    if "🅰" in texto or "factura a" in texto.lower() or texto.strip().upper() == "A":
        ctx.user_data["fac_tipo"] = "A"
    elif "🅱" in texto or "factura b" in texto.lower() or texto.strip().upper() == "B":
        ctx.user_data["fac_tipo"] = "B"
    else:
        await update.message.reply_text("⚠️ Elegí A o B usando los botones.")
        return FAC_TIPO
    await update.message.reply_text(
        f"✅ Factura tipo *{ctx.user_data['fac_tipo']}*\n\n"
        "✏️ *Nombre o Razón Social* del cliente:",
        parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())
    return FAC_CLIENTE_NOMBRE

async def fac_cliente_nombre(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    texto = await get_texto(update)
    if not texto: return FAC_CLIENTE_NOMBRE
    ctx.user_data["cliente_nombre"] = texto
    if ctx.user_data["fac_tipo"] == "A":
        await update.message.reply_text("✏️ *CUIT* del cliente (sin guiones):", parse_mode="Markdown")
    else:
        await update.message.reply_text("✏️ *DNI o CUIT* del cliente:\n_(o `-` si es consumidor final)_", parse_mode="Markdown")
    return FAC_CLIENTE_DOC

async def fac_cliente_doc(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    texto = await get_texto(update)
    if not texto: return FAC_CLIENTE_DOC
    from arca_handler import detectar_tipo_doc
    doc_tipo, doc_nro = detectar_tipo_doc(texto)
    if ctx.user_data["fac_tipo"] == "A" and doc_tipo != 80:
        await update.message.reply_text(
            "⚠️ Para *Factura A* el cliente debe tener CUIT (11 dígitos). Reingresá:",
            parse_mode="Markdown")
        return FAC_CLIENTE_DOC
    ctx.user_data["cliente_doc_tipo"] = doc_tipo
    ctx.user_data["cliente_doc_nro"]  = doc_nro
    if ctx.user_data["fac_tipo"] == "A":
        cond = "IVA Responsable Inscripto"
    elif doc_tipo == 80:
        cond = "Monotributista / Exento"
    else:
        cond = "Consumidor Final"
    ctx.user_data["cliente_cond_iva"] = cond

    # Si viene de conversión, los items ya están — saltar a confirmar
    if ctx.user_data.get("items") and ctx.user_data.get("conv_numero") is not None:
        return await _factura_resumen(update, ctx)
    if ctx.user_data.get("items"):  # viene de conversión (items precargados)
        return await _factura_resumen(update, ctx)

    await update.message.reply_text(
        f"✅ Cliente: {ctx.user_data['cliente_nombre']} ({cond})\n\n"
        "📦 Ítems.\n\n✏️ *Descripción* del ítem:",
        parse_mode="Markdown")
    return FAC_ITEM_DESC

async def fac_item_desc(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    texto = await get_texto(update)
    if not texto: return FAC_ITEM_DESC
    ctx.user_data["_item_desc"] = texto
    await update.message.reply_text("✏️ *Cantidad*:", parse_mode="Markdown")
    return FAC_ITEM_QTY

async def fac_item_qty(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    texto = await get_texto(update)
    if not texto: return FAC_ITEM_QTY
    qty = extraer_cantidad(texto)
    if qty is None:
        await update.message.reply_text("⚠️ No entendí la cantidad. Intentá de nuevo:")
        return FAC_ITEM_QTY
    ctx.user_data["_item_qty"] = qty
    if ctx.user_data["fac_tipo"] == "A":
        await update.message.reply_text("✏️ *Precio unitario SIN IVA*:", parse_mode="Markdown")
    else:
        await update.message.reply_text("✏️ *Precio unitario FINAL* (con IVA):", parse_mode="Markdown")
    return FAC_ITEM_PRECIO

async def fac_item_precio(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    texto = await get_texto(update)
    if not texto: return FAC_ITEM_PRECIO
    precio = extraer_numero(texto)
    if precio is None:
        await update.message.reply_text("⚠️ Precio inválido. Intentá de nuevo:")
        return FAC_ITEM_PRECIO
    ctx.user_data["_item_precio"] = precio
    await update.message.reply_text("✏️ *Alícuota de IVA*:", parse_mode="Markdown", reply_markup=teclado_iva())
    return FAC_ITEM_IVA

async def fac_item_iva(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    texto = await get_texto(update)
    if not texto: return FAC_ITEM_IVA
    alicuota = 10.5 if "10" in texto else 21.0
    qty    = ctx.user_data.pop("_item_qty")
    desc   = ctx.user_data.pop("_item_desc")
    precio = ctx.user_data.pop("_item_precio")
    ctx.user_data["items"].append({"desc": desc, "qty": qty, "precio": precio, "alicuota_iva": alicuota})
    resumen = "\n".join(
        f"  • {it['qty']}x {it['desc']} — {fmt_pesos(it['precio'])} ({it['alicuota_iva']}%)"
        for it in ctx.user_data["items"])
    await update.message.reply_text(
        f"✅ Ítem agregado.\n\n*Ítems:*\n{resumen}\n\n¿Agregar otro ítem?",
        parse_mode="Markdown", reply_markup=teclado_si_no())
    return FAC_MAS_ITEMS

async def fac_mas_items(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    texto = await get_texto(update)
    if not texto: return FAC_MAS_ITEMS
    if any(p in texto.lower() for p in ["sí","si","dale","otro","más","mas","quiero","yes"]):
        await update.message.reply_text("✏️ Descripción del siguiente ítem:", reply_markup=ReplyKeyboardRemove())
        return FAC_ITEM_DESC
    return await _factura_resumen(update, ctx)

async def _factura_resumen(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    items = ctx.user_data["items"]
    tipo = ctx.user_data["fac_tipo"]
    if tipo == "A":
        neto = sum(it["qty"]*it["precio"] for it in items)
        iva  = sum(it["qty"]*it["precio"]*(it["alicuota_iva"]/100) for it in items)
        total = neto + iva
    else:
        total = sum(it["qty"]*it["precio"] for it in items)
        neto  = sum(it["qty"]*it["precio"]/(1+it["alicuota_iva"]/100) for it in items)
        iva   = total - neto
    detalle = "\n".join(
        f"  • {it['qty']}x {it['desc']} — {fmt_pesos(it['precio'])} ({it['alicuota_iva']}%)"
        for it in items)
    await update.message.reply_text(
        f"🧾 *Resumen Factura {tipo}*\n\n"
        f"👤 {ctx.user_data['cliente_nombre']}\n"
        f"🪪 {ctx.user_data.get('cliente_doc_nro') or '-'}\n"
        f"📋 {ctx.user_data['cliente_cond_iva']}\n\n"
        f"*Ítems:*\n{detalle}\n\n"
        f"Neto: {fmt_pesos(round(neto,2))}\nIVA: {fmt_pesos(round(iva,2))}\n"
        f"*TOTAL: {fmt_pesos(round(total,2))}*\n\n"
        "⚠️ Una vez confirmada se emite en ARCA y NO se puede cancelar.\n¿Confirmás?",
        parse_mode="Markdown", reply_markup=teclado_si_no())
    return FAC_CONFIRMAR

async def fac_confirmar(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    texto = await get_texto(update)
    if not texto: return FAC_CONFIRMAR
    if any(p in texto.lower() for p in ["no","cancel"]):
        await update.message.reply_text("❌ Factura cancelada.", reply_markup=teclado_menu())
        ctx.user_data.clear(); return ConversationHandler.END
    await update.message.reply_text("⏳ Emitiendo factura en ARCA...", reply_markup=ReplyKeyboardRemove())
    try:
        from arca_handler import emitir_factura, generar_qr_afip, CUIT, HOMOLOGACION, TIPO_FACTURA_A, TIPO_FACTURA_B
        from pdf_generator import generar_factura_pdf
        resultado = emitir_factura(
            tipo=ctx.user_data["fac_tipo"],
            cliente_doc_tipo=ctx.user_data["cliente_doc_tipo"],
            cliente_doc_nro=ctx.user_data["cliente_doc_nro"],
            items=ctx.user_data["items"])
        tipo_cmp = TIPO_FACTURA_A if ctx.user_data["fac_tipo"] == "A" else TIPO_FACTURA_B
        qr_b64 = generar_qr_afip(
            cuit_emisor=CUIT, fecha=resultado["fecha"], pto_vta=resultado["punto_venta"],
            tipo=tipo_cmp, nro=resultado["numero"], importe=resultado["total"],
            doc_tipo=ctx.user_data["cliente_doc_tipo"], doc_nro=ctx.user_data["cliente_doc_nro"],
            cae=resultado["cae"])
        pdf_bytes = generar_factura_pdf(
            tipo=ctx.user_data["fac_tipo"], numero=resultado["numero"], punto_venta=resultado["punto_venta"],
            cae=resultado["cae"], vencimiento_cae=resultado["vencimiento_cae"], fecha=resultado["fecha"],
            cliente_nombre=ctx.user_data["cliente_nombre"], cliente_doc_tipo=ctx.user_data["cliente_doc_tipo"],
            cliente_doc_nro=ctx.user_data["cliente_doc_nro"], cliente_cond_iva=ctx.user_data["cliente_cond_iva"],
            items=ctx.user_data["items"], qr_b64=qr_b64, homologacion=HOMOLOGACION)
        nro_str = f"{resultado['punto_venta']:05d}-{resultado['numero']:08d}"
        await update.message.reply_document(
            document=io.BytesIO(pdf_bytes),
            filename=f"Factura{ctx.user_data['fac_tipo']}_{nro_str}_NeuronComputacion.pdf",
            caption=f"✅ *Factura {ctx.user_data['fac_tipo']} N° {nro_str}* emitida.\nCAE: `{resultado['cae']}`\n"
                    f"{'⚠️ HOMOLOGACIÓN — sin valor fiscal' if HOMOLOGACION else ''}",
            parse_mode="Markdown", reply_markup=teclado_menu())
    except Exception as e:
        logger.error(f"Error factura: {e}", exc_info=True)
        await update.message.reply_text(
            f"❌ Error al emitir:\n`{str(e)[:500]}`", parse_mode="Markdown", reply_markup=teclado_menu())
    ctx.user_data.clear(); return ConversationHandler.END

# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    db.init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    voz_o_texto = filters.TEXT | filters.VOICE | filters.AUDIO

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CommandHandler("presupuesto", iniciar_presupuesto),
            CommandHandler("comprobante", iniciar_comprobante),
            CommandHandler("factura", iniciar_factura),
            CommandHandler("convertir", convertir_presupuesto),
            MessageHandler(filters.Regex(r"(?i)(presupuesto|cotiz|📄)"), iniciar_presupuesto),
            MessageHandler(filters.Regex(r"(?i)(comprobante x|🧾 comprobante)"), iniciar_comprobante),
            MessageHandler(filters.Regex(r"(?i)(factura)"), iniciar_factura),
        ],
        states={
            MENU_PRINCIPAL:      [MessageHandler(voz_o_texto & ~filters.COMMAND, menu_handler)],
            PRES_CLIENTE_NOMBRE: [MessageHandler(voz_o_texto & ~filters.COMMAND, pres_cliente_nombre)],
            PRES_CLIENTE_DNI:    [MessageHandler(voz_o_texto & ~filters.COMMAND, pres_cliente_dni)],
            PRES_CLIENTE_TEL:    [MessageHandler(voz_o_texto & ~filters.COMMAND, pres_cliente_tel)],
            PRES_ITEM_DESC:      [MessageHandler(voz_o_texto & ~filters.COMMAND, pres_item_desc)],
            PRES_ITEM_QTY:       [MessageHandler(voz_o_texto & ~filters.COMMAND, pres_item_qty)],
            PRES_ITEM_PRECIO:    [MessageHandler(voz_o_texto & ~filters.COMMAND, pres_item_precio)],
            PRES_MAS_ITEMS:      [MessageHandler(voz_o_texto & ~filters.COMMAND, pres_mas_items)],
            PRES_NOTAS:          [MessageHandler(voz_o_texto & ~filters.COMMAND, pres_notas)],
            PRES_CONFIRMAR:      [MessageHandler(voz_o_texto & ~filters.COMMAND, pres_confirmar)],
            COMP_CLIENTE_NOMBRE: [MessageHandler(voz_o_texto & ~filters.COMMAND, comp_cliente_nombre)],
            COMP_CLIENTE_CUIT:   [MessageHandler(voz_o_texto & ~filters.COMMAND, comp_cliente_cuit)],
            COMP_CLIENTE_TEL:    [MessageHandler(voz_o_texto & ~filters.COMMAND, comp_cliente_tel)],
            COMP_ITEM_DESC:      [MessageHandler(voz_o_texto & ~filters.COMMAND, comp_item_desc)],
            COMP_ITEM_QTY:       [MessageHandler(voz_o_texto & ~filters.COMMAND, comp_item_qty)],
            COMP_ITEM_PRECIO:    [MessageHandler(voz_o_texto & ~filters.COMMAND, comp_item_precio)],
            COMP_MAS_ITEMS:      [MessageHandler(voz_o_texto & ~filters.COMMAND, comp_mas_items)],
            COMP_NOTAS:          [MessageHandler(voz_o_texto & ~filters.COMMAND, comp_notas)],
            COMP_CONFIRMAR:      [MessageHandler(voz_o_texto & ~filters.COMMAND, comp_confirmar)],
            FAC_TIPO:            [MessageHandler(voz_o_texto & ~filters.COMMAND, fac_tipo)],
            FAC_CLIENTE_NOMBRE:  [MessageHandler(voz_o_texto & ~filters.COMMAND, fac_cliente_nombre)],
            FAC_CLIENTE_DOC:     [MessageHandler(voz_o_texto & ~filters.COMMAND, fac_cliente_doc)],
            FAC_ITEM_DESC:       [MessageHandler(voz_o_texto & ~filters.COMMAND, fac_item_desc)],
            FAC_ITEM_QTY:        [MessageHandler(voz_o_texto & ~filters.COMMAND, fac_item_qty)],
            FAC_ITEM_PRECIO:     [MessageHandler(voz_o_texto & ~filters.COMMAND, fac_item_precio)],
            FAC_ITEM_IVA:        [MessageHandler(voz_o_texto & ~filters.COMMAND, fac_item_iva)],
            FAC_MAS_ITEMS:       [MessageHandler(voz_o_texto & ~filters.COMMAND, fac_mas_items)],
            FAC_CONFIRMAR:       [MessageHandler(voz_o_texto & ~filters.COMMAND, fac_confirmar)],
            CONV_NUMERO:         [MessageHandler(voz_o_texto & ~filters.COMMAND, conv_numero)],
            CONV_TIPO:           [MessageHandler(voz_o_texto & ~filters.COMMAND, conv_tipo)],
        },
        fallbacks=[CommandHandler("cancelar", cancelar)],
        allow_reentry=True,
    )
    app.add_handler(conv)
    app.add_handler(CommandHandler("ayuda", ayuda))
    logger.info("🚀 Bot Neuron Computación iniciado...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
