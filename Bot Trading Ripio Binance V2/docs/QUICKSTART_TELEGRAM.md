# Quick Start - Control Remoto Telegram

Guía rápida para configurar el control remoto del bot desde tu celular en **5 minutos**.

---

## Paso 1: Crear Bot en Telegram (2 min)

1. Abre Telegram en tu celular
2. Busca **@BotFather**
3. Envía `/newbot`
4. Cuando te pregunte el nombre, escribe: `Mi Trading Bot`
5. Cuando te pregunte el username, escribe: `mi_trading_bot_12345` (debe terminar en `bot` y ser único)
6. **BotFather te dará un TOKEN** - cópialo

```
Ejemplo de respuesta:
Done! Your bot token is:
tu_telegram_bot_token_aqui
```

---

## Paso 2: Obtener Tu User ID (1 min)

1. Busca **@userinfobot** en Telegram
2. Envíale `/start`
3. Te responderá con tu **User ID** - cópialo

```
Ejemplo de respuesta:
Id: 123456789
```

---

## Paso 3: Configurar .env (1 min)

Abre el archivo `.env` en tu proyecto y agrega estas líneas:

```bash
# Telegram Bot
TELEGRAM_BOT_TOKEN=tu_telegram_bot_token_aqui
TELEGRAM_AUTHORIZED_USERS=123456789
```

**Reemplaza**:
- `tu_telegram_bot_token_aqui` con el token que te dio BotFather
- `123456789` con tu User ID de @userinfobot

---

## Paso 4: Iniciar Bot (1 min)

En la terminal:

```bash
python main.py
```

Deberías ver en los logs:

```
[INIT] Inicializando Telegram Bot Interface...
[TELEGRAM] Bot initialized - Authorized users: 1
[TELEGRAM] Iniciando bot de Telegram...
```

---

## Paso 5: Probar desde el Celular

1. Abre Telegram
2. Busca tu bot (el nombre que pusiste, ej: `mi_trading_bot_12345`)
3. Envía `/start`

Deberías recibir:

```
[TRADING BOT INTERFACE]

Bienvenido al control remoto del bot de trading.

Comandos disponibles:
/help - Ver todos los comandos
/status - Estado del bot
/stats - Estadísticas de performance
/positions - Posiciones actuales

Control:
/startbot - Iniciar bot
/stopbot - Detener bot
/pause - Pausar estrategias
/resume - Reanudar estrategias
```

---

## ✅ Listo!

Ahora puedes controlar el bot desde tu celular.

### Comandos Más Usados

```
/status       → Ver si el bot está corriendo
/stats        → Ver Sharpe, P&L, Win Rate
/positions    → Ver posiciones abiertas
/trades       → Ver últimos trades
/pause        → Pausar todo
/resume       → Reanudar
```

---

## Activar Alertas Automáticas

Para recibir un resumen cada hora:

```
/alertson
```

Recibirás cada 60 minutos:

```
[PERIODIC UPDATE]

Sharpe (7d): 2.1
Total P&L: $156.78
Today P&L: $12.34
Today Trades: 3
```

Para desactivar:

```
/alertsoff
```

---

## Troubleshooting Rápido

### Bot no responde

**Solución**:
1. Verifica que el token en `.env` sea correcto
2. Reinicia el bot: `Ctrl+C` y luego `python main.py`
3. Busca errores en la terminal

### "No tienes permiso"

**Solución**:
1. Verifica tu User ID con @userinfobot
2. Agrégalo a `TELEGRAM_AUTHORIZED_USERS` en `.env`
3. Reinicia el bot

### No recibo alertas

**Solución**:
```
/alertson
```

---

## Próximos Pasos

Ver documentación completa: [TELEGRAM_INTERFACE.md](TELEGRAM_INTERFACE.md)

---

**Tiempo total**: 5 minutos

**Resultado**: Control completo del bot desde tu celular
