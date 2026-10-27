# Telegram Bot Interface - Control Remoto

## Descripción

Sistema de control remoto del trading bot vía Telegram que permite:
- Ver estadísticas en tiempo real desde el celular
- Controlar bot (start/stop/pause)
- Monitorear posiciones y trades
- Recibir alertas automáticas
- Recargar configuración
- Ejecutar backtests

---

## Configuración Inicial

### 1. Crear Bot de Telegram

1. Habla con [@BotFather](https://t.me/botfather) en Telegram
2. Envía `/newbot`
3. Elige un nombre para tu bot (ej: "Mi Trading Bot")
4. Elige un username (debe terminar en 'bot', ej: "mi_trading_bot")
5. BotFather te dará un **token** - guárdalo

**Ejemplo**:
```
BotFather: Done! Congratulations on your new bot.
Token: tu_telegram_bot_token_aqui
```

---

### 2. Obtener Tu User ID

1. Habla con [@userinfobot](https://t.me/userinfobot)
2. Te dirá tu User ID (número)

**Ejemplo**:
```
Id: 123456789
```

---

### 3. Configurar en .env

Agrega estas líneas a tu archivo `.env`:

```bash
# Telegram Bot
TELEGRAM_BOT_TOKEN=tu_telegram_bot_token_aqui
TELEGRAM_AUTHORIZED_USERS=123456789,987654321
```

**Notas**:
- `TELEGRAM_BOT_TOKEN`: Token que te dio BotFather
- `TELEGRAM_AUTHORIZED_USERS`: Tu User ID (puedes agregar varios separados por comas)

---

### 4. Instalar Dependencias

```bash
pip install python-telegram-bot
```

---

## Uso

### Iniciar Bot

Una vez configurado, el bot de Telegram se inicia automáticamente cuando ejecutas:

```bash
python main.py
```

Verás en los logs:
```
[INIT] Inicializando Telegram Bot Interface...
[TELEGRAM] Bot initialized - Authorized users: 1
[TELEGRAM] Iniciando bot de Telegram...
```

---

### Comandos Disponibles

#### Información

| Comando | Descripción | Ejemplo |
|---------|-------------|---------|
| `/start` | Mensaje de bienvenida | `/start` |
| `/help` | Lista de comandos | `/help` |
| `/status` | Estado del bot | `/status` |
| `/stats` | Estadísticas generales | `/stats` |
| `/pnl` | Profit & Loss breakdown | `/pnl` |
| `/positions` | Posiciones actuales | `/positions` |
| `/trades` | Últimos trades | `/trades` |
| `/strategies` | Estado de estrategias | `/strategies` |

#### Control del Bot

| Comando | Descripción | Ejemplo |
|---------|-------------|---------|
| `/startbot` | Iniciar bot de trading | `/startbot` |
| `/stopbot` | Detener bot | `/stopbot` |
| `/pause` | Pausar todas las estrategias | `/pause` |
| `/resume` | Reanudar estrategias | `/resume` |

#### Control de Estrategias

| Comando | Descripción | Ejemplo |
|---------|-------------|---------|
| `/enable <strategy>` | Activar estrategia específica | `/enable stat_arb` |
| `/disable <strategy>` | Desactivar estrategia | `/disable market_making` |

**Estrategias disponibles**:
- `stat_arb` - Statistical Arbitrage
- `market_making` - Market Making

#### Data Management

| Comando | Descripción | Ejemplo |
|---------|-------------|---------|
| `/reload` | Recargar configuración | `/reload` |
| `/backtest` | Ejecutar backtest | `/backtest` |
| `/collect` | Instrucciones para data collection | `/collect` |

#### Alertas

| Comando | Descripción | Ejemplo |
|---------|-------------|---------|
| `/alerts` | Toggle alertas on/off | `/alerts` |
| `/alertson` | Activar alertas | `/alertson` |
| `/alertsoff` | Desactivar alertas | `/alertsoff` |

---

## Ejemplos de Uso

### Ver Estado del Bot

```
Tú: /status

Bot:
[BOT STATUS]

Bot: RUNNING
Portfolio Value: $1,234.56 USD

Strategies:
Statistical Arbitrage: ON
Market Making: ON

Alertas: ON
Timestamp: 2026-01-16 14:30:00
```

---

### Ver Estadísticas

```
Tú: /stats

Bot:
[STATISTICS]

Sharpe Ratio (7d): 2.1
Total P&L: $156.78
Win Rate: 65.5%
Total Trades: 87
Max Drawdown: 4.2%

Today:
  Trades: 3
  P&L: $12.34

Last 7 days:
  Trades: 45
  P&L: $89.12
```

---

### Ver P&L Breakdown

```
Tú: /pnl

Bot:
[P&L BREAKDOWN]

Total: $156.78

By Strategy:
  Statistical Arb: $98.45
  Market Making: $58.33

By Time Period:
  Today: $12.34
  This Week: $89.12
  This Month: $156.78
```

---

### Ver Posiciones Actuales

```
Tú: /positions

Bot:
[POSITIONS]

USDT/USDC:
  Side: LONG USDT
  Size: $500.00
  Entry: $1.0015
  Current: $1.0020
  P&L: $2.50 (0.5%)
  Duration: 2h 15m
```

---

### Ver Últimos Trades

```
Tú: /trades

Bot:
[RECENT TRADES]

2026-01-16 12:00:00
statistical_arbitrage | USDT/USDC
LONG $500.00
P&L: $2.50

2026-01-16 10:30:00
market_making | USDT_ARS
SELL $200.00
P&L: $1.20
```

---

### Pausar Estrategias

```
Tú: /pause

Bot:
[SUCCESS]

Todas las estrategias pausadas.
Use /resume para reanudar.
```

---

### Activar/Desactivar Estrategia Específica

```
Tú: /disable stat_arb

Bot:
[SUCCESS] Statistical Arbitrage disabled

---

Tú: /enable stat_arb

Bot:
[SUCCESS] Statistical Arbitrage enabled
```

---

### Recargar Configuración

```
Tú: /reload

Bot:
[SUCCESS] Configuración recargada
```

Útil cuando modificaste `trading_config.yaml` y quieres aplicar cambios sin reiniciar el bot.

---

## Alertas Automáticas

El bot envía **alertas periódicas** automáticamente cada 60 minutos (configurable).

**Ejemplo de alerta**:
```
[PERIODIC UPDATE]

Sharpe (7d): 2.1
Total P&L: $156.78
Today P&L: $12.34
Today Trades: 3
```

### Configurar Intervalo de Alertas

En el código, puedes modificar:

```python
# En src/telegram/bot_interface.py, línea ~18
self.alert_interval_minutes = 60  # Cambiar a lo que quieras
```

---

## Seguridad

### Autorización por User ID

Solo los User IDs listados en `TELEGRAM_AUTHORIZED_USERS` pueden usar el bot.

**Si no configuras usuarios autorizados**, cualquiera que tenga el token podría controlar tu bot. **Siempre configura `TELEGRAM_AUTHORIZED_USERS`**.

### Si alguien no autorizado intenta usar el bot:

```
Bot: [UNAUTHORIZED]

No tienes permiso para usar este bot.
Tu user ID: 999999999
```

Y verás en los logs:
```
[TELEGRAM] Unauthorized access attempt from 999999999
```

---

## Troubleshooting

### Error: "Token inválido"

**Causa**: Token de Telegram incorrecto

**Solución**:
1. Verifica que copiaste el token completo de BotFather
2. No debe tener espacios ni saltos de línea
3. Formato correcto: `tu_telegram_bot_token_aqui` (ej. números seguidos de dos puntos y cadena alfanumérica)

---

### Error: "No response from bot"

**Causa**: Bot no está corriendo o no se inició Telegram interface

**Solución**:
1. Verifica que `TELEGRAM_BOT_TOKEN` esté en `.env`
2. Revisa los logs para ver si se inició correctamente
3. Busca línea: `[TELEGRAM] Bot initialized`

---

### Bot responde pero comandos no funcionan

**Causa**: No estás autorizado

**Solución**:
1. Obtén tu User ID de [@userinfobot](https://t.me/userinfobot)
2. Agrégalo a `TELEGRAM_AUTHORIZED_USERS` en `.env`
3. Reinicia el bot

---

### Alertas no llegan

**Causa**: Alertas desactivadas

**Solución**:
```
/alertson
```

---

## Funcionalidades Avanzadas

### 1. Múltiples Usuarios Autorizados

```bash
# En .env
TELEGRAM_AUTHORIZED_USERS=123456789,987654321,555555555
```

Todos los usuarios listados podrán controlar el bot.

---

### 2. Ejecutar Backtest Remoto

```
Tú: /backtest

Bot:
[BACKTEST STARTED]

Ejecutando backtest...
Esto puede tomar varios minutos.

[Después de unos minutos]

[BACKTEST COMPLETED]

Resultados:
Sharpe Ratio: 2.1
Total Trades: 87
Win Rate: 65.5%
Max Drawdown: 8.2%

Ver detalles en: reports/backtest_latest.txt
```

---

### 3. Ver Estado de Estrategias

```
Tú: /strategies

Bot:
[STRATEGIES]

Statistical Arbitrage:
  Status: ENABLED
  Allocation: 40.0%
  Z-Entry: 2.0
  Z-Exit: 0.5

Market Making:
  Status: ENABLED
  Allocation: 30.0%
  Spread Target: 10 bps
```

---

## Flujo Típico de Uso

### Mañana (Iniciar Bot)

```
1. Inicias bot en servidor:
   python main.py

2. Desde el celular:
   /status       # Verificar que está corriendo
   /stats        # Ver estadísticas
   /alertson     # Activar alertas
```

### Durante el Día (Monitoreo)

```
3. Recibes alertas periódicas automáticamente

4. Si quieres ver posiciones:
   /positions

5. Si quieres ver trades:
   /trades
```

### Si algo va mal:

```
6. Pausar estrategias:
   /pause

7. Revisar estado:
   /status
   /stats

8. Si es grave:
   /stopbot
```

### Noche (Revisión)

```
9. Ver resumen del día:
   /pnl
   /stats

10. Desactivar alertas si quieres dormir:
    /alertsoff
```

---

## Limitaciones Actuales

### 1. Backtest no implementado completamente

El comando `/backtest` está preparado, pero necesita integración con `run_backtest.py`.

**Para implementar**:
- Modificar `_run_backtest_task()` en `bot_interface.py`
- Ejecutar `run_backtest.py` vía subprocess
- Parsear resultados y enviarlos

---

### 2. Posiciones en vivo

`/positions` muestra datos del state, pero necesita precios actuales en vivo.

**TODO**: Integrar con APIs para obtener precios current y calcular P&L en tiempo real.

---

### 3. Data Collection

`/collect` solo muestra instrucciones. No inicia el collector automáticamente.

**Razón**: `collect_data.py` es un proceso separado que debe correrse aparte.

---

## Próximas Mejoras

### Funcionalidades a Agregar

1. **Gráficos**: Equity curve, P&L chart vía matplotlib
2. **Notificaciones de trades**: Alert cada vez que se ejecuta un trade
3. **Configuración vía comandos**: Cambiar parámetros sin editar archivos
4. **Multi-chat**: Soporte para grupos de Telegram
5. **Logs en tiempo real**: Ver últimas líneas del log desde Telegram

---

## Código de Ejemplo

### Enviar Alerta Manualmente

Desde cualquier parte del código del bot:

```python
# En una estrategia
if significant_event:
    if self.bot.telegram_bot:
        await self.bot.telegram_bot.send_alert(
            message="[STAT ARB] Z-score extremo detectado: 3.5"
        )
```

---

## Recursos

**Documentación Telegram Bot API**:
- [python-telegram-bot](https://docs.python-telegram-bot.org/)
- [Telegram Bot API](https://core.telegram.org/bots/api)

**Tutoriales**:
- [Create your first bot](https://core.telegram.org/bots/tutorial)
- [python-telegram-bot examples](https://github.com/python-telegram-bot/python-telegram-bot/tree/master/examples)

---

## Resumen

### Setup Rápido

1. Crear bot con @BotFather → Obtener token
2. Obtener tu User ID con @userinfobot
3. Agregar a `.env`:
   ```bash
   TELEGRAM_BOT_TOKEN=your_token
   TELEGRAM_AUTHORIZED_USERS=your_user_id
   ```
4. `pip install python-telegram-bot`
5. `python main.py`
6. Hablar con tu bot en Telegram: `/start`

### Comandos Esenciales

- `/status` - Ver estado
- `/stats` - Ver estadísticas
- `/positions` - Ver posiciones
- `/pause` - Pausar estrategias
- `/resume` - Reanudar
- `/stopbot` - Detener bot

### Alertas

- Se envían cada 60 minutos automáticamente
- Toggle con `/alerts`
- Desactivar: `/alertsoff`
- Activar: `/alertson`

---

**Última actualización**: 2026-01-16

**Estado**: Implementado y funcional

**Próximo**: Integrar backtest remoto y gráficos
