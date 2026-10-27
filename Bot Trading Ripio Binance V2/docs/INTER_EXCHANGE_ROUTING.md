# Inter-Exchange Routing - Documentación

## Problema

Swap USDC ↔ USDT en Ripio tiene costos elevados:
- **Spread**: 20-100 ARS típico (vs 0.01% en Binance)
- **Slippage**: Alto por baja liquidez
- **Fee**: 0.30% taker (casi siempre)

**Resultado**: Conversión ineficiente, pérdida de profit en arbitraje.

---

## Solución: Inter-Exchange Router

Sistema que decide automáticamente:
- **Ripio directo**: Si spread es pequeño
- **Vía Binance**: Si spread es grande

---

## Cómo Funciona

### Ruta Ripio Directo
```
Costo = Spread + Trading Fee
      = (ask - bid) + (0.30% * amount)
```

**Ventajas**:
- Instantáneo (1 min)
- Sin network fees
- Simple

**Desventajas**:
- Spread amplio
- Slippage alto

---

### Ruta Binance
```
1. Ripio → Withdraw USDC → Binance (network fee: $1.50 TRC20)
2. Binance: Swap USDC → USDT 1:1 (fee: 0.1%)
3. Binance → Withdraw USDT → Ripio (network fee: $1.50 TRC20)

Costo = $1.50 + $1.50 + (0.1% * amount) = $3 + 0.1%
```

**Ventajas**:
- Swap casi 1:1 (spread 0.01%)
- Fee 3x más barato (0.1% vs 0.30%)
- Alta liquidez (no slippage)

**Desventajas**:
- Network fees: $3 USD (TRC20)
- Tiempo: 30-60 min
- Complejidad

---

## Decisión Automática

### Fórmula
```python
# Ripio cost
ripio_cost = amount * (spread_pct + 0.30%)

# Binance cost
binance_cost = $3 + (amount * 0.10%)

# Decision
if ripio_cost < binance_cost:
    route = RIPIO_DIRECT
else:
    route = BINANCE_ROUTE
```

### Ejemplo 1: Spread Pequeño (20 ARS)
```
Amount: $500 USD
Spread: 20 ARS = 0.013 USD = 0.0026%

Ripio:
  Spread: $0.013
  Fee: $1.50 (0.30%)
  Total: $1.51

Binance:
  Network: $3.00
  Fee: $0.50 (0.10%)
  Total: $3.50

✅ RIPIO DIRECTO ($1.51 < $3.50)
```

---

### Ejemplo 2: Spread Grande (200 ARS)
```
Amount: $500 USD
Spread: 200 ARS = 0.13 USD = 0.026%

Ripio:
  Spread: $0.13
  Fee: $1.50 (0.30%)
  Total: $1.63

Binance:
  Network: $3.00
  Fee: $0.50 (0.10%)
  Total: $3.50

✅ RIPIO DIRECTO ($1.63 < $3.50)
```

**Nota**: Solo con spreads MUY grandes (> 1%) conviene Binance.

---

### Ejemplo 3: Monto Grande + Spread Moderado
```
Amount: $10,000 USD
Spread: 50 ARS = 0.033 USD = 0.00033%

Ripio:
  Spread: $0.33
  Fee: $30.00 (0.30%)
  Total: $30.33

Binance:
  Network: $3.00
  Fee: $10.00 (0.10%)
  Total: $13.00

✅ BINANCE ROUTE ($13.00 < $30.33)
```

**Conclusión**: Con montos grandes (> $5,000), casi siempre conviene Binance.

---

## Configuración

### trading_config.yaml
```yaml
routing:
  # Margen de seguridad (ganancia debe ser > 1.5x costo)
  min_profit_margin: 1.5

  # Red blockchain preferida
  preferred_network: trc20  # Tron (más barato)

  # Network fees por token
  network_fees:
    usdt:
      erc20: 12.0  # Ethereum (caro)
      trc20: 1.5   # Tron (recomendado)
      bep20: 1.0   # BSC
    usdc:
      erc20: 10.0
      trc20: 1.5
      bep20: 1.0
```

---

## Uso

### Automático (recomendado)
El bot decide automáticamente:

```python
# Statistical Arbitrage usa router internamente
stat_arb_strategy = StatisticalArbitrageStrategy(
    ripio_api=ripio_api,
    router=router  # Router se encarga de decisión
)
```

**Logs**:
```
[ROUTER] Calculating route: USDC → USDT ($500.00)
[ROUTER] ✅ RIPIO DIRECT - Cost: $1.51
[STAT ARB] Executed via ripio_direct
```

---

### Manual (testing)
```python
from execution import InterExchangeRouter

router = InterExchangeRouter(ripio_api, binance_api, config)

# Calcular ruta óptima
route = await router.calculate_optimal_route(
    from_token='USDC',
    to_token='USDT',
    amount_usd=500
)

print(f"Route: {route['route_type']}")
print(f"Cost: ${route['total_cost_usd']:.2f}")
print(f"Profitable: {route['is_profitable']}")

# Ejecutar
if route['is_profitable']:
    result = await router.execute_optimal_route('USDC', 'USDT', 500)
```

---

## Métricas Clave

### Break-Even Point
```
Network fee: $3 (TRC20)
Ahorro fee: 0.30% - 0.10% = 0.20%

Break-even: $3 / 0.20% = $1,500 USD

Conclusión:
- Si amount < $1,500 → Probablemente Ripio
- Si amount > $1,500 → Probablemente Binance
```

### Redes Blockchain Comparadas
| Red | USDT Fee | USDC Fee | Velocidad | Recomendación |
|-----|----------|----------|-----------|---------------|
| **TRC20** (Tron) | $1.50 | $1.50 | 5-10 min | ✅ Recomendado |
| **BEP20** (BSC) | $1.00 | $1.00 | 3-5 min | ✅ Alternativa |
| **ERC20** (ETH) | $12.00 | $10.00 | 10-20 min | ❌ Muy caro |

---

## Limitaciones Actuales

### 1. Solo Simulación
```python
async def execute_binance_route(...):
    # TODO: Implementar ejecución real
    logger.info("Step 1/3: Withdraw (simulated)")
    logger.info("Step 2/3: Swap (simulated)")
    logger.info("Step 3/3: Withdraw (simulated)")
```

**Para producción**:
- Implementar Ripio withdraw API
- Implementar Binance deposit detection
- Implementar swap en Binance
- Monitoring de confirmaciones blockchain

---

### 2. Sin Datos Reales de Spread
```python
# Necesita datos históricos de Ripio
spread_info = await router.get_ripio_swap_spread('USDT', 'USDC')
```

**TODO**: Obtener 30 días de datos históricos para calcular spread típico.

---

### 3. Timing Variable
- Confirmaciones blockchain: 10-30 min (variable)
- Oportunidad puede cerrarse mientras transferimos
- Necesita predicción de duración de spread

---

## Próximos Pasos

### Fase 1: Recolección de Datos ⏳
```bash
# Obtener 30 días de datos USDT/USDC en Ripio
# Calcular spread promedio, máximo, mínimo
# Determinar cuándo realmente conviene Binance route
```

### Fase 2: Implementación Real ⏳
```python
# Implementar:
- Ripio withdrawal (USDC/USDT → Binance)
- Binance swap execution
- Binance withdrawal (USDT/USDC → Ripio)
- Monitoring de deposits/confirmaciones
```

### Fase 3: Optimización ⏳
```python
# Agregar:
- Predicción de duración de spread (ML)
- Multiple network fallback (TRC20 → BEP20)
- Parallel execution (multiple swaps)
- Cost history tracking
```

---

## Comandos Útiles

### Ver Status del Router
```python
router.get_status()
# Output:
# {
#   'preferred_network': 'trc20',
#   'min_profit_margin': 1.5,
#   'ripio_taker_fee': 0.0030,
#   'binance_swap_fee': 0.0010,
#   'network_fees': {...}
# }
```

### Simular Decisión (Sin Ejecutar)
```python
route = await router.calculate_optimal_route('USDC', 'USDT', 1000)
# No ejecuta, solo calcula ruta óptima
```

---

## Referencias

- **Ripio API**: https://developers.ripiotrade.co/
- **Binance Swap API**: https://binance-docs.github.io/apidocs/spot/en/#convert-endpoints
- **Network Fees**: https://withdrawalfees.com/

---

**Última actualización**: 2026-01-15
**Estado**: ✅ Implementado (simulación)
**Próximo**: Obtener datos reales de spread Ripio
