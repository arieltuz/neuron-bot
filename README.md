# 🤖 Bot Telegram — Neuron Computación

Bot de Telegram para generar documentos comerciales (presupuestos, comprobantes y facturas electrónicas) con reconocimiento de voz en español.

---

## ✨ Funcionalidades

### 📄 Presupuestos
- Datos del cliente (nombre, DNI/CUIT, teléfono)
- Ítems con descripción, cantidad y precio unitario
- Total sin desglose de IVA (precios finales)
- Observaciones opcionales
- PDF con logo y diseño profesional
- Se guardan en base de datos para conversión posterior

### 🧾 Comprobante X
- Datos del cliente (nombre, CUIT, teléfono)
- Ítems con descripción, cantidad y precio unitario
- Total directo sin IVA
- **Firma digital** de Firmante autorizado centrada en el documento
- PDF con logo y diseño profesional

### 🅰️🅱️ Factura Electrónica (ARCA/AFIP)
- Factura A (Responsables Inscriptos) y Factura B (Consumidores Finales)
- Integración con WSAA + WSFEv1 de ARCA (ex-AFIP)
- Obtención automática de CAE
- QR oficial de AFIP incrustado en el PDF
- Soporte para alícuotas de IVA 21% y 10.5%
- Modo homologación y producción

### 🔄 Convertir Presupuesto
- Comando `/convertir <número>` para convertir un presupuesto aprobado
- Busca automáticamente los datos del presupuesto guardado
- Genera Comprobante X o Factura A/B sin recargar ningún dato
- Botones **inline** para evitar conflictos con el menú principal

### 🎙️ Reconocimiento de Voz
- Transcripción offline con **Vosk** (gratis, sin API externa)
- Modelo español `vosk-model-small-es-0.42` (~40MB, descarga automática)
- Conversión de audio con ffmpeg (ogg → wav 16kHz mono)
- Función `extraer_numero()` para convertir palabras a números

---

## 📁 Estructura del proyecto

```
neuron-bot/
├── bot.py              # Lógica principal del bot
├── pdf_generator.py    # Generador de PDFs (Presupuesto, Comprobante X, Factura)
├── voice_handler.py    # Transcripción de audio con Vosk
├── arca_handler.py     # Integración ARCA (WSAA + WSFEv1)
├── db.py               # Base de datos PostgreSQL + fallback JSON
├── logo_neuron.png     # Logo del local
├── firma_mario.png     # Firma digital para Comprobante X
├── requirements.txt    # Dependencias Python
├── nixpacks.toml       # Configuración de build (ffmpeg, openssl)
├── Procfile            # Comando de inicio para Railway
├── railway.json        # Configuración de deploy
└── .gitignore          # Excluye certificados y datos sensibles
```

---

## ⚙️ Variables de entorno (Railway)

| Variable | Descripción |
|---|---|
| `TELEGRAM_TOKEN` | Token del bot (obtener de @BotFather) |
| `DATABASE_URL` | URL de PostgreSQL (Railway lo genera automáticamente) |
| `ARCA_HOMOLOGACION` | `true` para testing, `false` para producción |
| `ARCA_PUNTO_VENTA` | Número de punto de venta (ej: `3`) |
| `ARCA_KEY_B64` | Clave privada en base64 |
| `ARCA_CERT_HOMO_B64` | Certificado de homologación en base64 |
| `ARCA_CERT_PROD_B64` | Certificado de producción en base64 |

> ⚠️ **NUNCA** pongas el token ni credenciales hardcodeadas en el código. Siempre usá variables de entorno.

---

## 🗄️ Base de datos

El bot usa **PostgreSQL** en Railway para persistir:
- **Presupuestos** — guardados con todos los datos del cliente e ítems
- **Contadores correlativos** — para numeración de presupuestos y comprobantes

Si no hay `DATABASE_URL` disponible (entorno local), usa archivos JSON como fallback automático.

### Tablas creadas automáticamente al iniciar:
```sql
CREATE TABLE contadores (tipo TEXT PRIMARY KEY, valor INTEGER DEFAULT 0);
CREATE TABLE presupuestos (numero TEXT PRIMARY KEY, datos JSONB, creado TIMESTAMP);
```

---

## 💬 Comandos del bot

| Comando | Descripción |
|---|---|
| `/start` | Menú principal |
| `/presupuesto` | Nuevo presupuesto |
| `/comprobante` | Nuevo Comprobante X |
| `/factura` | Nueva Factura Electrónica A/B |
| `/convertir <número>` | Convierte un presupuesto en comprobante o factura |
| `/cancelar` | Cancela la operación actual |
| `/ayuda` | Muestra todos los comandos |

---

## 🚀 Deploy en Railway

### 1. Clonar el repo y conectar a Railway
```bash
railway login
railway link
```

### 2. Agregar PostgreSQL
En Railway → tu proyecto → **+ New** → **Database** → **PostgreSQL**

Railway asigna `DATABASE_URL` automáticamente al servicio del bot.

### 3. Configurar variables de entorno
En Railway → tu servicio → **Variables**:
```
TELEGRAM_TOKEN=tu_token_aqui
ARCA_HOMOLOGACION=true
ARCA_PUNTO_VENTA=3
```

### 4. Deploy
Railway redeploya automáticamente con cada push a `main`.

---

## 🔐 Certificados ARCA (para facturación electrónica)

### Generar certificados (una sola vez):
```bash
openssl genrsa -out neuron.key 2048
openssl req -new -key neuron.key \
  -subj "/C=AR/O=Matias H Carabajal/CN=neuron-bot/serialNumber=CUIT XXXXXXXXXXX" \
  -out neuron.csr
```

### Subir CSR a ARCA homologación:
1. Entrar a https://wsass-homo.afip.gob.ar/wsass/portal/main.aspx
2. Subir `neuron.csr` → Descargar `neuron-homo.crt`

### Convertir a base64 (PowerShell):
```powershell
[Convert]::ToBase64String([IO.File]::ReadAllBytes("neuron.key")) | Set-Clipboard
[Convert]::ToBase64String([IO.File]::ReadAllBytes("neuron-homo.crt")) | Set-Clipboard
```

### Subir a Railway como variables:
- `ARCA_KEY_B64` → contenido base64 de `neuron.key`
- `ARCA_CERT_HOMO_B64` → contenido base64 de `neuron-homo.crt`

---

## 📦 Dependencias

```
python-telegram-bot==21.6
reportlab==4.2.5
Pillow==10.4.0
vosk==0.3.45
zeep==4.2.1
qrcode==7.4.2
psycopg2-binary==2.9.9
```

Sistema: `ffmpeg` y `openssl` (instalados via nixpacks)

---

## 🏪 Datos del local

- **Local:** Neuron Computación
- **Titular:** Titular del local
- **CUIT:** XX-XXXXXXXX-X
- **IVA:** Responsable Inscripto
- **Dirección:** Dirección del local
- **Tel:** XXXXXXXXXX
- **Email:** correo@ejemplo.com

---

## 🔒 Seguridad

- El token de Telegram **nunca** debe estar hardcodeado en el código
- El repositorio debe ser **privado** en GitHub
- Los certificados ARCA (`.key`, `.crt`) están excluidos del repo via `.gitignore`
- Usar siempre variables de entorno para credenciales

---

## 📝 Notas técnicas

- Los botones del flujo `/convertir` usan **InlineKeyboardMarkup** para evitar conflictos con los entry_points del ConversationHandler
- El reconocimiento de voz descarga el modelo Vosk automáticamente en `models/` la primera vez que se usa (~40MB, tarda 1-2 min extra en el primer arranque)
- La numeración de presupuestos y comprobantes es atómica en PostgreSQL (sin duplicados aunque haya requests concurrentes)
