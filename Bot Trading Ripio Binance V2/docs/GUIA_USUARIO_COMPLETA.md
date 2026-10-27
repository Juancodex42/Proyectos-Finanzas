# 📱 Guía Completa del Usuario - Bot de Trading Automático

## 🎯 Lo que el Bot Hace por Ti (Automáticamente)

### ✅ Ya NO necesitas hacer en la PC:

1. **Backtest completo** → Ahora desde Telegram con `/backtest`
2. **Ver estadísticas** → Todo en Telegram con `/stats`, `/pnl`, `/positions`
3. **Monitorear performance** → El bot te avisa automáticamente
4. **Detectar problemas** → Alertas automáticas si algo va mal
5. **Mantenimiento semanal** → Se hace solo cada Lunes

---

## 🚀 Setup Inicial (Solo 1 Vez)

### Paso 1: Configurar Telegram (5 minutos)

Ya está LISTO ✅ - Tu bot de Telegram está configurado:
- Token: `YOUR_TELEGRAM_BOT_TOKEN_HERE`
- Tu User ID: `YOUR_TELEGRAM_USER_ID_HERE`

### Paso 2: Iniciar Recolección de Datos

**En tu PC/Servidor** (solo este comando):
```bash
python collect_data.py --mode continuous --interval 5
```

**¿Qué hace?**
- Guarda precios cada 5 minutos
- Crea archivos diarios automáticamente
- NO usa tu dinero (solo observa)

**Déjalo corriendo 30 días** (o mínimo 7 para empezar)

### Paso 3: Iniciar el Bot

```bash
python main.py
```

**Listo!** 🎉 Ahora TODO se controla desde el celular.

---

## 📱 Comandos de Telegram - Guía Rápida

### 🔍 Ver Información

```
/status       → ¿Está corriendo? ¿Cuánto capital?
/stats        → Sharpe, P&L, Win Rate, Trades
/pnl          → Ganancias por estrategia y período
/positions    → Operaciones abiertas ahora
/trades       → Últimos 5 trades
/collect      → Progreso de recolección de datos
```

**Ejemplo de lo que verás**:
```
/stats

[STATISTICS]

Sharpe Ratio (7d): 2.1 ⭐⭐
Total P&L: $156.78
Win Rate: 65.5% ✅
Total Trades: 87
Max Drawdown: 4.2%

Today:
  Trades: 3
  P&L: $12.34

Last 7 days:
  Trades: 45
  P&L: $89.12
```

### 🎮 Controlar el Bot

```
/startbot     → Iniciar trading
/stopbot      → Detener todo
/pause        → Pausar estrategias
/resume       → Reanudar
```

### 🔧 Gestión Avanzada

```
/backtest     → Análisis completo (resultados en Telegram!)
/reload       → Recargar configuración
/strategies   → Ver estado de cada estrategia
/enable stat_arb      → Activar estrategia específica
/disable market_making → Desactivar estrategia
```

### 🔔 Alertas

```
/alertson     → Activar notificaciones
/alertsoff    → Desactivar
/alerts       → Toggle on/off
```

---

## 🤖 Lo que el Bot Hace AUTOMÁTICAMENTE

### 1️⃣ Monitoreo Continuo (Cada Hora)

El bot verifica automáticamente:
- ✅ Sharpe Ratio
- ✅ Drawdown
- ✅ Performance vs backtest

**Si detecta problemas, te avisa**:

```
🔴 [CRITICAL]

Métrica: Max Drawdown
Drawdown crítico: 16.5% (límite: 15%)

Acción recomendada:
DETENER BOT INMEDIATAMENTE

[Auto-pausando estrategias...]
```

### 2️⃣ Mantenimiento Semanal (Lunes 9 AM)

**El bot ejecuta automáticamente**:
1. Verifica datos históricos
2. Ejecuta backtest con datos nuevos
3. Compara con performance actual
4. Te envía un reporte completo

**Ejemplo de reporte que recibirás**:

```
📋 [REPORTE SEMANAL AUTOMÁTICO]
2026-01-20 09:00

1️⃣ DATOS HISTÓRICOS
✅ Status: OK
Días de datos: 30
Última actualización: 2026-01-20

2️⃣ BACKTEST AUTOMÁTICO
✅ Completado
Sharpe: 2.1
Win Rate: 65.5%
Max DD: 8.2%
Trades: 87

3️⃣ COMPARACIÓN LIVE vs BACKTEST
Sharpe Backtest: 2.1
Sharpe Live (7d): 1.9
✅ Degradación: 9.5%

4️⃣ RECOMENDACIONES
✅ Performance dentro de lo esperado.
Continuar operando normalmente.
```

### 3️⃣ Alertas Periódicas (Cada 60 min)

Si activaste alertas con `/alertson`, recibes:

```
[PERIODIC UPDATE]

Sharpe (7d): 2.1
Total P&L: $156.78
Today P&L: $12.34
Today Trades: 3
```

**Puedes cambiar la frecuencia**:
- Default: Cada 60 minutos
- Desactivar: `/alertsoff`
- Reactivar: `/alertson`

### 4️⃣ Detección Automática de Degradación

Si la estrategia empieza a fallar:

**Nivel 1 - Advertencia (Degradación > 30%)**:
```
⚠️ [WARNING]

Métrica: Sharpe Ratio
Sharpe bajando: 1.4 (objetivo: >1.5)

Acción recomendada:
Monitorear de cerca
```

**Nivel 2 - Crítico (Degradación > 50%)**:
```
🔴 [CRITICAL]

Métrica: Sharpe Ratio
Sharpe muy bajo: 0.9 (umbral: 1.0)

Acción recomendada:
Pausar estrategias y revisar

[ESTRATEGIAS PAUSADAS AUTOMÁTICAMENTE]
```

---

## 📊 /backtest - Análisis Completo desde Telegram

### ¿Cómo funciona?

1. Envías `/backtest` desde el celular
2. El bot te va actualizando el progreso
3. Al final recibes resultados completos

### Lo que verás:

**Paso 1**:
```
📊 Paso 1/4: Verificando datos históricos...
```

**Paso 2**:
```
📥 Paso 2/4: Cargando 30 días de datos...
```

**Paso 3**:
```
🔄 Paso 3/4: Ejecutando backtest...
(Esto puede tardar 1-2 minutos)
```

**Paso 4**:
```
📈 Paso 4/4: Generando resultados...
```

**Resultado Final**:
```
✅ [BACKTEST COMPLETADO]

📅 Período: 30 días
📊 Datos: 8,640 registros

RESULTADOS:
Sharpe Ratio: 2.1 ⭐⭐
Win Rate: 65.5% ✅
Max Drawdown: 8.2% ✅
Total Trades: 87
Avg Trade: $12.34

COMPARACIÓN CON LIVE:
Sharpe Live (7d): 1.9
Degradación: 9.5% ✅

RECOMENDACIÓN:
✅ Performance dentro de lo esperado.
Continuar operando normalmente.

Usa /stats para ver métricas actuales.
```

---

## 📊 /collect - Ver Progreso de Datos

### Si NO tienes datos aún:

```
📊 [RECOLECCIÓN DE DATOS]

❌ No tienes datos históricos aún.

CÓMO EMPEZAR:
1. En tu servidor/PC, ejecuta:
   python collect_data.py --mode continuous --interval 5

2. Déjalo corriendo 30 días
3. El bot guardará datos cada 5 minutos

⏱️ Necesitas mínimo 7 días para backtest
🎯 Objetivo: 30 días para análisis completo
```

### Si tienes pocos datos (ej: 3 días):

```
📊 [ESTADO DE DATOS]

📅 Días recolectados: 3/30
⏱️ Faltan: 27 días

⚠️ Necesitas 7 días mínimo para backtest
✅ Te faltan 4 días

PROGRESO: ▓▓▓░░░░░░░░░░░░░░░░░░░░░░░░░░░ 10%

💡 Sigue recolectando datos.
El collector debe estar corriendo en tu servidor.
```

### Si tienes suficientes datos (ej: 15 días):

```
📊 [ESTADO DE DATOS]

📅 Días recolectados: 15/30
✅ Ya puedes hacer backtest!

PROGRESO: ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░░ 50%

Opciones:
• /backtest - Ejecutar análisis ahora
• Esperar 30 días - Resultados más precisos

💡 Te recomiendo esperar 15 días más.
```

### Si tienes datos completos (30+ días):

```
📊 [ESTADO DE DATOS]

✅ COMPLETO!
📅 Días recolectados: 30
📆 Último dato: 2026-01-20

PROGRESO: ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ 100%

🎯 Tienes suficientes datos para:
• Backtest completo
• Walk-Forward Analysis
• Monte Carlo Simulation

Siguiente paso:
/backtest - Analizar datos
```

---

## 🗓️ Rutina Diaria (Super Simple)

### Mañana (2 minutos):
```
1. /status     → Verificar que está corriendo
2. /stats      → Ver cómo va
3. /alertson   → Activar notificaciones del día
```

### Durante el Día:
- **Recibes alertas automáticas cada hora**
- **Si hay problema crítico, el bot se pausa solo**
- No necesitas hacer nada más

### Noche (2 minutos):
```
1. /pnl        → Cuánto ganaste/perdiste hoy
2. /trades     → Ver últimas operaciones
3. /alertsoff  → (Opcional) Desactivar para dormir
```

---

## 📅 Rutina Semanal (AUTOMÁTICA)

### Lunes 9 AM:
- El bot hace mantenimiento automático
- Recibes reporte semanal en Telegram
- Si hay problema, te avisa qué hacer

### Tú solo revisas el reporte:

**Si dice "TODO OK" ✅**:
- No hacer nada
- Seguir operando normal

**Si dice "WARNING" ⚠️**:
- Revisar `/stats` con más frecuencia
- Considerar `/backtest` manual

**Si dice "CRITICAL" 🔴**:
- El bot YA pausó las estrategias
- Revisar qué cambió
- Decidir si continuar o no

---

## 🎯 Qué Hacer en Cada Situación

### ✅ Si TODO va bien (Sharpe > 2.0):

```
NADA - Dejar que trabaje solo
```

### ⚠️ Si performance baja (Sharpe 1.5-2.0):

```
1. /backtest    → Ver si es temporal
2. Monitorear 3-5 días más
3. Si no mejora → /pause
```

### 🔴 Si va mal (Sharpe < 1.0):

```
1. /pause       → Pausar inmediatamente
2. /backtest    → Analizar qué pasó
3. Revisar logs en PC
4. Decidir: Ajustar parámetros o Detener
```

### 🛑 Si pierde mucho (Drawdown > 10%):

```
1. /stopbot     → Detener TODO
2. Revisar qué salió mal
3. NO reactivar hasta entender el problema
```

---

## 💡 Tips de Uso

### 1. Deja que el Bot Trabaje

- El bot monitorea 24/7
- Te avisa si hay problemas
- NO necesitas revisar cada hora

### 2. Confía en las Alertas Automáticas

- Si no recibes alerta crítica = Todo OK
- Las alertas periódicas son informativas
- Solo actúa si recibes 🔴 CRITICAL

### 3. No Cambies Parámetros Sin Razón

- Si funciona, déjalo así
- Solo ajusta si hay degradación confirmada
- Usa `/backtest` antes de cambiar algo

### 4. Escala Gradualmente

- Semana 1-2: $100
- Semana 3-4: $250
- Si sigue bien: $500, $1000, etc.
- NUNCA pongas todo tu capital de una

### 5. Mantén Datos Actualizados

- El collector debe correr siempre
- Cada Lunes, verifica `/collect`
- Si faltan datos, reinicia collector

---

## 🆘 Problemas Comunes

### "Bot no responde en Telegram"

**Solución**:
```
1. Verifica que main.py está corriendo
2. En la PC, mira los logs
3. Busca: [TELEGRAM] Bot initialized
```

### "Backtest dice 'Datos insuficientes'"

**Solución**:
```
1. /collect → Ver cuántos días tienes
2. Si < 7 días: Esperar más tiempo
3. Verificar que collect_data.py está corriendo
```

### "Recibo alerta CRITICAL"

**Acción**:
```
1. NO entrar en pánico
2. El bot ya pausó estrategias
3. Envía /stats para ver detalles
4. Revisa el reporte semanal
5. Decide si continuar o detener
```

### "No recibo alertas periódicas"

**Solución**:
```
1. /alertson
2. Espera 60 minutos
3. Si no llega, verifica que main.py corre
```

---

## 📋 Checklist de Mantenimiento

### Diario (Automático):
- ✅ Bot monitorea Sharpe, Drawdown
- ✅ Alertas cada hora (si activadas)
- ✅ Auto-pausa si problema crítico

### Semanal (Automático):
- ✅ Backtest con datos nuevos
- ✅ Comparación Live vs Backtest
- ✅ Reporte completo en Telegram
- ✅ Recomendaciones de acción

### Mensual (Manual - 10 minutos):
- [ ] Revisar logs completos en PC
- [ ] Verificar que collector sigue corriendo
- [ ] Backup de datos históricos
- [ ] Actualizar código si hay mejoras

---

## 🎯 Resumen Ultra-Rápido

### Setup (1 vez):
```
1. Iniciar collect_data.py en PC
2. Esperar 7-30 días
3. Iniciar main.py
4. Listo - Todo desde Telegram
```

### Uso Diario:
```
Mañana: /status, /stats, /alertson
Durante día: Bot te avisa si hay problemas
Noche: /pnl, /alertsoff
```

### Uso Semanal:
```
Lunes: Recibes reporte automático
Revisar reporte → Decidir acción
```

### Comandos Esenciales:
```
/status    → ¿Está corriendo?
/stats     → ¿Cómo va?
/backtest  → Análisis completo
/collect   → Progreso de datos
/pause     → Pausar emergencia
/stopbot   → Detener todo
```

---

## 🚀 Ventajas del Sistema Automático

✅ **Desde Telegram**:
- Backtest completo con resultados
- Todas las estadísticas
- Control total del bot
- Alertas inteligentes

✅ **Automático**:
- Monitoreo 24/7
- Mantenimiento semanal
- Detección de problemas
- Pausado automático si falla

✅ **Amigable**:
- Mensajes claros
- Progreso visual
- Recomendaciones específicas
- Explicaciones simples

✅ **Sin PC**:
- 90% del tiempo usas solo el celular
- PC solo para iniciar collector y bot
- Todo lo demás: Telegram

---

**¡Ya está todo listo!** 🎉

Ahora puedes operar el bot completamente desde tu celular, y él se encarga del monitoreo y mantenimiento automático.

**Próximo paso**: Busca tu bot en Telegram y envía `/start`
