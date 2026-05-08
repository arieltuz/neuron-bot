# 🤖 Bot Telegram — Neuron Computación

Genera **Presupuestos** y **Comprobantes X** en PDF directamente desde Telegram.

---

## 📁 Estructura de archivos

```
neuron_bot/
├── bot.py              ← Lógica del bot
├── pdf_generator.py    ← Generador de PDFs
├── logo_neuron.png     ← Logo del local (COPIAR AQUÍ)
├── requirements.txt    ← Dependencias Python
├── counters.json       ← Se crea automáticamente (numeración)
└── README.md
```

---

## ⚙️ Instalación paso a paso

### 1. Instalar Python

Necesitás **Python 3.10 o superior**.
→ Descargalo desde: https://www.python.org/downloads/

### 2. Instalar dependencias

Abrí una terminal (cmd o PowerShell en Windows) dentro de la carpeta `neuron_bot` y ejecutá:

```bash
pip install -r requirements.txt
```

### 3. Copiar el logo

Copiá el archivo `logo_neuron.png` dentro de la carpeta `neuron_bot/`.
*(Ya está incluido si descargaste el ZIP completo)*

### 4. Pegar el token del bot

Abrí el archivo `bot.py` con cualquier editor de texto (Bloc de notas, VS Code, etc.).

Buscá esta línea:
```python
BOT_TOKEN = os.environ.get("TELEGRAM_TOKEN", "PEGA_TU_TOKEN_AQUI")
```

Reemplazá `PEGA_TU_TOKEN_AQUI` con el token que te dio BotFather, por ejemplo:
```python
BOT_TOKEN = os.environ.get("TELEGRAM_TOKEN", "123456789:AAFxxxxxxxxxxxxxxxxxxxxxxxx")
```

Guardá el archivo.

### 5. Ejecutar el bot

```bash
python bot.py
```

Deberías ver en la terminal:
```
Bot Neuron Computación iniciado...
```

---

## 📱 Cómo usarlo en Telegram

1. Buscá tu bot por el username que le pusiste al crearlo
2. Escribí `/start`
3. Usá los botones para elegir **Presupuesto** o **Comprobante X**
4. El bot te va a ir pidiendo los datos paso a paso
5. Al confirmar, te manda el PDF directamente al chat

### Comandos disponibles
| Comando | Descripción |
|---|---|
| `/start` | Abre el menú principal |
| `/presupuesto` | Inicia un presupuesto nuevo |
| `/comprobante` | Inicia un Comprobante X nuevo |
| `/cancelar` | Cancela la operación actual |
| `/ayuda` | Muestra la ayuda |

---

## 🔄 Mantener el bot corriendo

Para que el bot funcione continuamente sin que tengas que dejarlo abierto en tu PC:

### Opción A — PC siempre encendida (más simple)
Simplemente dejá la terminal abierta con el bot corriendo.

### Opción B — Servidor VPS (recomendado)
Podés contratar un servidor VPS barato (desde ~$2 USD/mes en Contabo, DigitalOcean, etc.) y correr el bot ahí.

### Opción C — Railway.app (gratis)
1. Creá cuenta en https://railway.app
2. Subí la carpeta como proyecto
3. Configurá la variable de entorno `TELEGRAM_TOKEN` con tu token
4. El bot corre automáticamente 24/7

---

## 🛠️ Personalización

Para cambiar los datos del local, editá el diccionario `LOCAL` en `pdf_generator.py`:

```python
LOCAL = {
    "nombre":    "Neuron Computación",
    "titular":   "Matías H. Carabajal",
    "cuit":      "20-29535790-9",
    "iva":       "IVA Responsable Inscripto",
    "tel":       "3731444804",
    "email":     "neuroncomputacion@gmail.com",
    "direccion": "Mariano Moreno 463",
}
```

---

## ❓ Problemas frecuentes

**El bot no responde:**
- Verificá que el token en `bot.py` sea correcto
- Asegurate de que la terminal siga abierta

**Error al generar PDF:**
- Verificá que `logo_neuron.png` esté en la misma carpeta que `bot.py`

**Error de módulo no encontrado:**
- Ejecutá nuevamente: `pip install -r requirements.txt`
