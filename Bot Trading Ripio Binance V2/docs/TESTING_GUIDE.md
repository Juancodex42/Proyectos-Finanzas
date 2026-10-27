# 🧪 GUÍA DE PRUEBAS - BOT V2.0

Esta guía te llevará paso a paso para verificar que todo funciona correctamente.

---

## 📋 PREREQUISITOS

Antes de empezar, asegúrate de tener:
- ✅ Python 3.10+ instalado
- ✅ Credenciales de Ripio Trade API
- ✅ Token de bot de Telegram
- ✅ Git Bash o terminal compatible

---

## 🚀 PASO 1: Configuración Inicial

### 1.1 Navegar al directorio del bot
```bash
cd "Bot Trading Ripio Binance V2"
```

### 1.2 Crear entorno virtual (recomendado)
```bash
python -m venv venv
.\venv\Scripts\activate  # Windows
```

### 1.3 Instalar dependencias
```bash
pip install -r requirements.txt
```

**Salida esperada:**
```
Successfully installed aiohttp-3.9.1 numpy-1.24.3 pandas-2.0.3 ...
```

---

## 🔐 PASO 2: Configurar Credenciales

### 2.1 Copiar template de .env
```bash
copy .env.example .env
```

### 2.2 Editar .env con tus credenciales

Abre `.env` con un editor de texto y reemplaza:

```env
# TELEGRAM
BOT_TOKEN=tu_bot_token_aqui          ← Token de @BotFather
CHAT_ID=tu_chat_id_aqui              ← Tu Telegram Chat ID

# RIPIO TRADE API
RIPIO_API_TOKEN=tu_ripio_api_token   ← API Key de Ripio Trade
RIPIO_SECRET_KEY=tu_secret_key       ← Secret Key de Ripio Trade

# MODO
TRADING_MODE=paper_trading           ← IMPORTANTE: Dejar en paper_trading

# CAPITAL
CAPITAL_INICIAL=1000                 ← Capital inicial (USD)
```

**💡 Cómo obtener credenciales de Ripio:**
1. Ir a https://app.ripiotrade.co/settings/api-keys
2. Crear nueva API Key
3. Copiar Token y Secret Key

---

## 🧪 PASO 3: Ejecutar Test Suite

### 3.1 Ejecutar todos los tests
```bash
python test_bot.py
```

### 3.2 Interpretar resultados

**TEST 1: Estructura de Archivos**
```
✅ Archivo: .env.example
✅ Archivo: config/trading_config.yaml
✅ Archivo: src/core/ripio_api.py
...
```
**Esperado:** Todos ✅

---

**TEST 2: Configuración**
```
✅ Archivo .env existe
✅ Credenciales cargadas
✅ Variable BOT_TOKEN
✅ Variable RIPIO_API_TOKEN
...
```

**Si ves ❌:**
- `❌ Archivo .env existe` → Ejecuta `copy .env.example .env`
- `❌ Variable XXX` → Falta configurar esa variable en .env

---

**TEST 3: Conexión a APIs**
```
📡 Probando Ripio API...
✅ Ripio API health check
✅ Ripio get_ticker('USDT_ARS')
   ℹ️  Precio: $1,234.56
✅ Ripio get_orderbook('USDT_ARS')
   ℹ️  5 bids, 5 asks
✅ Ripio get_balance()
   ℹ️  3 monedas
```

**Si ves ❌:**
- `❌ Ripio API health check` → Verificar credenciales en .env
- `❌ get_ticker` → Verificar conexión a internet
- `❌ get_balance` → Verificar permisos de API Key

---

**TEST 4: State Manager**
```
✅ State Manager load_state()
✅ State Manager update_capital()
✅ State Manager save_state()
```
**Esperado:** Todos ✅

---

**TEST 5: Portfolio Manager**
```
✅ Portfolio actualizar_inventario()
✅ Portfolio actualizar_precios()
✅ Portfolio calcular_valor_portfolio_usd()
   ℹ️  Valor: $1,234.56
```

**Output esperado:**
```
📊 PORTFOLIO STATUS
━━━━━━━━━━━━━━━━━━━━━━━━━
💰 Valor Total: $1,234.56 USD
📈 P&L Total: $0.00

💼 Inventario:
├─ USDT: 50.0000 ($50.00)
├─ USDC: 30.0000 ($30.00)
├─ ARS: 500,000.0000 ($400.00)
...
```

---

### 3.3 Resumen de tests

**Output final esperado:**
```
📊 RESUMEN DE TESTS
══════════════════════════════════════════════════════
Total tests: 25
✅ Passed: 25
❌ Failed: 0
Success rate: 100.0%
══════════════════════════════════════════════════════

🎉 TODOS LOS TESTS PASARON - BOT LISTO PARA USAR
```

**Si success rate < 100%:**
1. Revisa los tests con ❌
2. Corrige el problema indicado
3. Vuelve a ejecutar `python test_bot.py`

---

## 🤖 PASO 4: Ejecutar Bot en Modo Demo

Una vez que todos los tests pasen:

```bash
python main.py
```

### 4.1 Salida esperada

```
============================================================
🤖 BOT DE TRADING CUANTITATIVO V2.0
============================================================
📋 Cargando configuración...
✅ Modo: paper_trading
✅ Capital inicial: $1000.00

🔌 Inicializando APIs...
✅ Ripio API session initialized
✅ Binance API session initialized

🏥 Verificando conexión a APIs...
✅ Ripio API: Health check OK
✅ Binance API: Health check OK

💾 Inicializando State Manager...
💰 Capital actual: $1000.00

💼 Inicializando Portfolio Manager...
💼 Inventario actualizado:
   USDT: 50.0000
   USDC: 30.0000
   ARS: 500000.0000

============================================================
✅ BOT INICIALIZADO CORRECTAMENTE
============================================================

============================================================
📊 MODO DEMO - VERIFICACIÓN DE COMPONENTES
============================================================

1️⃣ Probando Ripio API...
   ✅ Ticker USDT/ARS: $1,234.56
   ✅ Orderbook: 5 bids, 5 asks
   ✅ Balance obtenido: 3 monedas

2️⃣ Probando Binance API...
   ✅ BTC/USDT: $67,890.12

3️⃣ Probando Portfolio Manager...
   ✅ Valor total: $1,234.56

📊 PORTFOLIO STATUS
━━━━━━━━━━━━━━━━━━━━━━━━━
💰 Valor Total: $1,234.56 USD
📈 P&L Total: $0.00
...

============================================================
✅ DEMO COMPLETADO - TODOS LOS COMPONENTES FUNCIONAN
============================================================

🛑 Cerrando bot...
💾 Estado guardado
🔒 Ripio API session closed
🔒 Binance API session closed
✅ Bot cerrado correctamente
```

---

## ✅ VERIFICACIÓN FINAL

### Checklist de funcionamiento:

- [ ] Test suite pasa 100%
- [ ] Bot se inicializa sin errores
- [ ] APIs responden correctamente
- [ ] Portfolio Manager muestra inventario
- [ ] Estado se guarda en `data/state/bot_state.json`
- [ ] Logs se crean en `data/logs/bot.log`

### Si todo ✅:

```
🎉 ¡FELICITACIONES!

El Bot V2.0 está funcionando correctamente.

Próximos pasos:
1. Revisar data/logs/bot.log para ver logs detallados
2. Revisar data/state/bot_state.json para ver estado guardado
3. Ajustar config/trading_config.yaml según necesites
4. Cuando estés listo, implementar estrategias de trading
```

---

## 🔧 TROUBLESHOOTING

### Problema: "ModuleNotFoundError: No module named 'aiohttp'"
**Solución:**
```bash
pip install -r requirements.txt
```

### Problema: "❌ Error cargando configuración"
**Solución:**
1. Verificar que `.env` existe
2. Verificar que todas las variables están configuradas
3. Verificar que no hay espacios extra en .env

### Problema: "❌ Ripio API no responde"
**Solución:**
1. Verificar credenciales en .env
2. Ir a Ripio Trade → Settings → API Keys
3. Verificar que API Key tiene permisos de lectura/trading
4. Regenerar API Key si es necesario

### Problema: "JSONDecodeError" al iniciar
**Solución:**
```bash
# Borrar estado corrupto
del data\state\bot_state.json
# Volver a ejecutar
python main.py
```

### Problema: Rate limit 429
**Solución:**
- Normal durante tests intensivos
- El bot espera automáticamente
- Reducir frecuencia de requests en tests

---

## 📞 SOPORTE

### Ver logs en tiempo real:
```bash
# Windows PowerShell
Get-Content data/logs/bot.log -Wait -Tail 50

# Git Bash
tail -f data/logs/bot.log
```

### Ver estado actual:
```bash
# Windows
type data\state\bot_state.json

# Git Bash
cat data/state/bot_state.json
```

### Limpiar y reiniciar:
```bash
# Borrar logs
del data\logs\*.log

# Borrar estado
del data\state\bot_state.json

# Volver a ejecutar
python test_bot.py
```

---

## 🎯 SIGUIENTE FASE

Una vez que todos los tests pasen, estás listo para:

1. **Implementar estrategias** (Statistical Arbitrage, Market Making)
2. **Configurar backtesting** (Monte Carlo, Walk-Forward)
3. **Ejecutar paper trading** (7 días mínimo)
4. **Ir a live trading** (empezar con $100)

**¡Éxito!** 🚀
