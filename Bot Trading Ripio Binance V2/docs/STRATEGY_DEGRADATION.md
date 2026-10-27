# Degradación de Estrategias - Detección y Respuesta

## ¿Qué es degradación?

**Degradación**: Estrategia que funcionaba deja de funcionar

```
Backtest (30 días pasados):  Sharpe 2.3
Paper (7 días):              Sharpe 1.9  ← Degradación 17% (OK)
Live (primeros 7 días):      Sharpe 0.8  ← Degradación 65% (MALO)
```

---

## Causas de Degradación

### 1. Overfitting (más común)
```
Ajustaste parámetros a ruido aleatorio de esos 30 días específicos.

Ejemplo:
├─ z_entry = 2.327 (demasiado específico)
└─ Funciona en esos 30 días, falla en siguientes
```

**Solución**: Usar parámetros "redondos" basados en teoría
- z_entry = 2.0 (no 2.327)
- lookback = 100 (no 97)

---

### 2. Cambio de Régimen
```
Mercado cambia de comportamiento:

Antes (baja volatilidad):
├─ Spread USDT/USDC: 10-20 ARS
└─ Estrategia funciona

Después (crisis):
├─ Spread USDT/USDC: 200-500 ARS
└─ Estrategia falla (z-score siempre alto)
```

**Solución**: Ajustar parámetros al nuevo régimen

---

### 3. Competencia
```
Otros bots empiezan a operar lo mismo:

Antes:
├─ Z-score llega a 2.5 (oportunidad dura 30 min)
└─ Tienes tiempo de ejecutar

Después:
├─ Z-score llega a 2.1 (oportunidad dura 10 seg)
└─ Otros bots arbitran más rápido
```

**Solución**:
- Bajar latencia (más rápido)
- Usar umbrales más bajos (entrar antes)

---

### 4. Cambio en Exchange
```
Ripio cambió algo:

Ejemplos:
├─ Aumentó fees de 0.30% a 0.50%
├─ Redujo liquidez en USDC
├─ Agregó delays en ejecución
└─ Cambió API (errores)
```

**Solución**: Revisar qué cambió, adaptar

---

## Sistema de Detección Automática

### Ya Implementado ✅

#### 1. Sharpe Ratio Monitoring

**Archivo**: `src/analytics/performance_tracker.py` (si existe)

```python
def check_degradation(sharpe_backtest, sharpe_live_7d):
    degradation = (sharpe_backtest - sharpe_live_7d) / sharpe_backtest

    if degradation > 0.50:
        return "CRITICAL - Stop trading"
    elif degradation > 0.30:
        return "WARNING - Review strategy"
    else:
        return "OK"
```

---

#### 2. Walk-Forward Validation

**Propósito**: Detectar si estrategia es robusta a cambios temporales

```python
# Divide en 4 períodos
Período 1: Sharpe 2.1
Período 2: Sharpe 1.9
Período 3: Sharpe 2.3
Período 4: Sharpe 0.5  ← ALERTA: Inconsistente

Conclusión: Estrategia NO es robusta
```

**Si pasa Walk-Forward** → Menos probable degradar

---

#### 3. Monte Carlo Simulation

**Propósito**: Ver distribución de resultados posibles

```
1000 simulaciones:
├─ P(Sharpe > 1.0) = 89%
└─ Si en live Sharpe < 1.0 → Mala suerte o degradación?

Si Sharpe live = 0.5 (peor que 89% de simulaciones):
└─ Probablemente degradación real
```

---

#### 4. Cointegration Testing (ongoing)

```python
# Statistical Arbitrage revisa cointegración cada semana
coint_result = check_cointegration(usdt_prices, usdc_prices)

if coint_result.p_value > 0.05:
    logger.warning("Cointegration broken - Strategy invalid")
    # Deshabilitar estrategia automáticamente
```

**Implementación**: Agregar a `run_strategies_loop()`

---

## Respuestas Automáticas (a implementar)

### Nivel 1: Alertas

```python
# Cuando Sharpe baja 30%
if sharpe_live < sharpe_backtest * 0.7:
    send_telegram_alert("WARNING: Performance degradation detected")
    log_detailed_metrics()
```

---

### Nivel 2: Reducción de Capital

```python
# Cuando Sharpe baja 40%
if sharpe_live < sharpe_backtest * 0.6:
    # Reducir allocation de 40% a 20%
    strategy.allocation_pct *= 0.5
    send_telegram_alert("CAUTION: Capital allocation reduced")
```

---

### Nivel 3: Pausa Automática

```python
# Cuando Sharpe baja 50% O max_dd excedido
if (sharpe_live < sharpe_backtest * 0.5) or (drawdown > 0.15):
    strategy.enabled = False
    send_telegram_alert("CRITICAL: Strategy paused automatically")
    # Cerrar posiciones abiertas
```

---

### Nivel 4: Re-Optimización

```python
# Cada semana, re-calcular parámetros óptimos
def weekly_reoptimization():
    # Últimos 30 días de datos
    recent_data = load_last_30_days()

    # Re-backtest con diferentes parámetros
    best_params = grid_search(recent_data)

    # Si mejora > 20% vs actuales
    if best_params.sharpe > current_sharpe * 1.2:
        # Actualizar parámetros (con aprobación manual)
        suggest_new_params(best_params)
```

⚠️ **CUIDADO**: No hacer esto automáticamente → Overfitting

---

## Protocolo Manual de Respuesta

### Semana 1-2 (Monitoreo)

```
Checklist diario:
├─ Sharpe live vs backtest
├─ Win rate
├─ Max drawdown
└─ Número de trades

Si todo OK → Continuar
```

---

### Semana 3-4 (Alerta temprana)

```
Si Sharpe < 1.5 (antes era 2.0):

1. Revisar logs: ¿Qué trades fallaron?
2. Verificar cointegración: ¿Sigue válida?
3. Check competencia: ¿Spreads más chicos?
4. Revisar fees: ¿Ripio cambió algo?

Si problema identificado → Ajustar
Si no → Esperar más datos
```

---

### Semana 5-6 (Acción)

```
Si Sharpe < 1.0 (degradación confirmada):

OPCIÓN A: Ajustar parámetros
├─ Re-backtest con últimos 30 días
├─ Encontrar z_entry óptimo para régimen actual
└─ Testear 7 días más en paper

OPCIÓN B: Cambiar estrategia
├─ Desactivar Stat Arb
├─ Enfocarse en Market Making
└─ Explorar nuevas estrategias

OPCIÓN C: Parar
├─ Si nada funciona → Stop
└─ Recolectar más datos, re-diseñar
```

---

## Indicadores de Salud (Dashboard)

### Métricas a Monitorear

```yaml
health_indicators:
  # Performance
  sharpe_ratio_7d: 1.8          # Target: > 1.5
  sharpe_ratio_30d: 2.0         # Target: > 1.5
  degradation_pct: 10%          # Target: < 30%

  # Risk
  max_drawdown: 4.2%            # Target: < 15%
  var_95: 1.8%                  # Target: < 2%

  # Activity
  trades_per_day: 3.5           # Target: 2-10
  avg_trade_duration: 2.3h      # Target: < 6h

  # Market Conditions
  usdt_usdc_cointegration: 0.03 # Target: < 0.05
  avg_spread_bps: 18            # Target: > 10
  volatility: 0.021             # Target: 0.01-0.05
```

**Semáforo**:
- 🟢 Verde: Todos los targets cumplidos
- 🟡 Amarillo: 1-2 targets fallando
- 🔴 Rojo: 3+ targets fallando → Acción requerida

---

## Código a Implementar

### 1. PerformanceMonitor (nuevo)

```python
# src/analytics/performance_monitor.py

class PerformanceMonitor:
    def __init__(self, strategy, backtest_sharpe):
        self.strategy = strategy
        self.backtest_sharpe = backtest_sharpe
        self.trades_window = deque(maxlen=100)

    def check_health(self) -> Dict:
        # Calcular Sharpe live últimos 7 días
        sharpe_live = self.calculate_live_sharpe()

        # Degradación
        degradation = (self.backtest_sharpe - sharpe_live) / self.backtest_sharpe

        # Status
        if degradation > 0.50:
            status = "CRITICAL"
            action = "PAUSE_STRATEGY"
        elif degradation > 0.30:
            status = "WARNING"
            action = "REDUCE_ALLOCATION"
        else:
            status = "OK"
            action = "CONTINUE"

        return {
            'status': status,
            'action': action,
            'sharpe_live': sharpe_live,
            'sharpe_backtest': self.backtest_sharpe,
            'degradation_pct': degradation * 100
        }
```

---

### 2. Auto-Pause Strategy

```python
# En main.py, dentro de run_strategies_loop()

async def run_strategies_loop(self):
    while True:
        # Ejecutar estrategias
        await self.stat_arb_strategy.run_iteration()

        # Check health cada hora
        if iteration % 60 == 0:
            health = self.monitor.check_health()

            if health['status'] == 'CRITICAL':
                logger.critical(f"[HEALTH] {health['action']}")
                self.stat_arb_strategy.enabled = False
                # Enviar alerta
```

---

### 3. Weekly Re-Calibration Report

```python
# Cada lunes a las 00:00
def generate_weekly_report():
    # Métricas últimos 7 días
    report = {
        'sharpe': calculate_sharpe_7d(),
        'trades': count_trades_7d(),
        'pnl': calculate_pnl_7d(),
        'cointegration': check_cointegration(),
        'spread_avg': calculate_avg_spread()
    }

    # Comparar con backtest
    comparison = compare_with_backtest(report)

    # Enviar por Telegram
    send_telegram(format_report(report, comparison))
```

---

## Conclusión

### Degradación es NORMAL

- ✅ Esperada: 10-30% en primeras semanas
- ⚠️ Preocupante: 30-50%
- 🛑 Crítica: >50%

### Sistema de 3 Capas

1. **Detección**: Monitoring automático 24/7
2. **Respuesta**: Alertas + Ajustes automáticos
3. **Prevención**: Walk-Forward + Monte Carlo en backtest

### Checklist Semanal

```
Lunes:
├─ Revisar Sharpe últimos 7 días
├─ Comparar vs backtest
├─ Check cointegración
└─ Decidir: Continuar / Ajustar / Pausar

Si todo OK → Nada que hacer
Si degradación → Protocolo de respuesta
```

---

**Última actualización**: 2026-01-15

**Próximo**: Implementar PerformanceMonitor y alertas automáticas
