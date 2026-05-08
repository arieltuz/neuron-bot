"""
Bot de Telegram - Neuron Computación
Genera Comprobantes X y Presupuestos en PDF
Soporta comandos de voz en español via OpenAI Whisper
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

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN  = os.environ.get("TELEGRAM_TOKEN", "8362308263:AAGA2gxYn-qCjtxO9rbOhBvTPELl8Yu52ro")
OPENAI_KEY = os.environ.get("OPENAI_API_KEY",  "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")
os.environ.setdefault("OPENAI_API_KEY", OPENAI_KEY)

(
    MENU_PRINCIPAL,
    PRES_CLIENTE_NOMBRE, PRES_CLIENTE_DNI, PRES_CLIENTE_TEL,
    PRES_ITEM_DESC, PRES_ITEM_QTY, PRES_ITEM_PRECIO,
    PRES_MAS_ITEMS, PRES_NOTAS, PRES_CONFIRMAR,
    COMP_CLIENTE_NOMBRE, COMP_CLIENTE_CUIT, COMP_CLIENTE_TEL,
    COMP_ITEM_DESC, COMP_ITEM_QTY, COMP_ITEM_PRECIO,
    COMP_MAS_ITEMS, COMP_NOTAS, COMP_CONFIRMAR,
) = range(19)

COUNTERS_FILE = Path(__file__).parent / "counters.json"

def load_counters():
    if COUNTERS_FILE.exists():
        with open(COUNTERS_FILE) as f: return json.load(f)
    return {"presupuesto": 0, "comprobante": 0}

def save_counters(c):
    with open(COUNTERS_FILE, "w") as f: json.dump(c, f)

def next_number(tipo):
    c = load_counters(); c[tipo] += 1; save_counters(c)
    return str(c[tipo]).zfill(4)

def fmt_pesos(v):
    return f"$ {v:,.2f}".replace(",","X").replace(".",",").replace("X",".")

def teclado_si_no():
    return ReplyKeyboardMarkup([["✅ Sí","❌ No"]], resize_keyboard=True, one_time_keyboard=True)

def teclado_menu():
    return ReplyKeyboardMarkup([["📄 Presupuesto","🧾 Comprobante X"],["❓ Ayuda"]], resize_keyboard=True)

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
            error_str = str(e)[:200]
            await msg.reply_text(
                f"⚠️ Error al transcribir el audio:\n`{error_str}`\n\nProbá escribir el texto.",
                parse_mode="Markdown"
            )
            return None
    return msg.text.strip() if msg.text else None

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 ¡Hola! Soy el bot de *Neuron Computación*.\n\n"
        "Podés escribirme o mandarme un 🎙️ *mensaje de voz*.\n\n¿Qué querés generar?",
        parse_mode="Markdown", reply_markup=teclado_menu())
    return MENU_PRINCIPAL

async def ayuda(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📋 *Comandos:*\n/start /presupuesto /comprobante /cancelar\n\n"
        "🎙️ También podés hablar en cualquier paso.\n"
        "Decí por ejemplo: _\"quiero un presupuesto\"_ o _\"haceme un comprobante\"_",
        parse_mode="Markdown", reply_markup=teclado_menu())
    return MENU_PRINCIPAL

async def cancelar(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.clear()
    await update.message.reply_text("❌ Operación cancelada.", reply_markup=teclado_menu())
    return MENU_PRINCIPAL

async def menu_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    texto = await get_texto(update)
    if not texto: return MENU_PRINCIPAL
    tl = texto.lower()
    if any(p in tl for p in ["presupuesto","presupu","cotiz","precio"]):
        return await iniciar_presupuesto(update, ctx)
    elif any(p in tl for p in ["comprobante","factura","recibo","ticket","venta","compro"]):
        return await iniciar_comprobante(update, ctx)
    elif any(p in tl for p in ["ayuda","help","?"]):
        return await ayuda(update, ctx)
    else:
        await update.message.reply_text(
            "No entendí 😅 Decí *\"presupuesto\"* o *\"comprobante\"*, o usá los botones 👇",
            parse_mode="Markdown", reply_markup=teclado_menu())
        return MENU_PRINCIPAL

# ── PRESUPUESTO ───────────────────────────────────────────────────────────────
async def iniciar_presupuesto(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.clear(); ctx.user_data["tipo"] = "presupuesto"; ctx.user_data["items"] = []
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
    subtotal = sum(it["qty"]*it["precio"] for it in items)
    iva = subtotal*0.21; total = subtotal+iva
    detalle = "\n".join(f"  • {it['qty']}x {it['desc']} — {fmt_pesos(it['precio'])} c/u" for it in items)
    await update.message.reply_text(
        f"📄 *Resumen Presupuesto*\n\n"
        f"👤 {ctx.user_data.get('cliente_nombre','-')}\n"
        f"🪪 {ctx.user_data.get('cliente_dni','-')}\n"
        f"📞 {ctx.user_data.get('cliente_tel','-')}\n\n"
        f"*Ítems:*\n{detalle}\n\n"
        f"Subtotal: {fmt_pesos(subtotal)}\nIVA 21%: {fmt_pesos(iva)}\n*TOTAL: {fmt_pesos(total)}*\n\n"
        f"📝 {ctx.user_data.get('notas','-')}\n\n¿Confirmás y generás el PDF?",
        parse_mode="Markdown", reply_markup=teclado_si_no())
    return PRES_CONFIRMAR

async def pres_confirmar(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    texto = await get_texto(update)
    if not texto: return PRES_CONFIRMAR
    if any(p in texto.lower() for p in ["no","cancel"]):
        await update.message.reply_text("❌ Cancelado.", reply_markup=teclado_menu())
        ctx.user_data.clear(); return MENU_PRINCIPAL
    numero = next_number("presupuesto")
    await update.message.reply_text("⏳ Generando PDF...", reply_markup=ReplyKeyboardRemove())
    pdf_bytes = generar_presupuesto_pdf(
        numero=numero, cliente_nombre=ctx.user_data.get("cliente_nombre","-"),
        cliente_dni=ctx.user_data.get("cliente_dni","-"), cliente_tel=ctx.user_data.get("cliente_tel","-"),
        items=ctx.user_data["items"], notas=ctx.user_data.get("notas",""))
    await update.message.reply_document(
        document=io.BytesIO(pdf_bytes), filename=f"Presupuesto_{numero}_NeuronComputacion.pdf",
        caption=f"✅ *Presupuesto N° {numero}* generado.", parse_mode="Markdown", reply_markup=teclado_menu())
    ctx.user_data.clear(); return MENU_PRINCIPAL

# ── COMPROBANTE X ─────────────────────────────────────────────────────────────
async def iniciar_comprobante(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.clear(); ctx.user_data["tipo"] = "comprobante"; ctx.user_data["items"] = []
    await update.message.reply_text(
        "🧾 *Nuevo Comprobante X*\n\nPaso 1/3 — Datos del cliente\n\n"
        "✏️ *Nombre completo* del cliente:",
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
        ctx.user_data.clear(); return MENU_PRINCIPAL
    numero = next_number("comprobante")
    await update.message.reply_text("⏳ Generando PDF...", reply_markup=ReplyKeyboardRemove())
    pdf_bytes = generar_comprobante_x_pdf(
        numero=numero, cliente_nombre=ctx.user_data.get("cliente_nombre","-"),
        cliente_cuit=ctx.user_data.get("cliente_cuit","-"), cliente_tel=ctx.user_data.get("cliente_tel","-"),
        items=ctx.user_data["items"], notas=ctx.user_data.get("notas",""))
    await update.message.reply_document(
        document=io.BytesIO(pdf_bytes), filename=f"ComprobanteX_{numero}_NeuronComputacion.pdf",
        caption=f"✅ *Comprobante X N° {numero}* generado.", parse_mode="Markdown", reply_markup=teclado_menu())
    ctx.user_data.clear(); return MENU_PRINCIPAL

# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    voz_o_texto = filters.TEXT | filters.VOICE | filters.AUDIO
    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CommandHandler("presupuesto", iniciar_presupuesto),
            CommandHandler("comprobante", iniciar_comprobante),
            MessageHandler(voz_o_texto & ~filters.COMMAND, menu_handler),
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
        },
        fallbacks=[CommandHandler("cancelar", cancelar)],
        allow_reentry=False,
    )
    app.add_handler(conv)
    app.add_handler(CommandHandler("ayuda", ayuda))
    logger.info("🚀 Bot Neuron Computación con voz iniciado...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
