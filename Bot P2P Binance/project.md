# Bot P2P Binance ARS — High-Frequency Market Making & Arbitrage Platform

## Descripción General
Plataforma algorítmica de nivel institucional para la provisión automatizada de liquidez, market making dinámico y arbitraje de rescate en el mercado **Binance P2P (ARS/USDT)**. Integra escaneo concurrente de carteleras por canal de pago (Mercado Pago, Bancos tradicionales y Fintechs), posicionamiento dinámico Book-Aware, escalera de ventas anti-colisión multi-anuncio (Opción A / High Rotation Ladder) conforme a la Regla 5.1 de Binance, blindaje estricto de Break-Even sobre costo promedio ponderado de compra (WAC) y conexión con oráculos externos (Fiwind / CriptoYa).

---

## Arquitectura del Proyecto

```
Bot P2P Binance/
├── docs/                               # Documentación técnica y diagramas de arquitectura
├── scripts/                            # Scripts de demostración y benchmarks
│   └── run_demo_showcase.py            # Demostración en vivo Zero-API
├── src/
│   ├── config/                         # Ajustes y parámetros demo/académicos
│   │   ├── settings.py                 # Parámetros sanitizados de microestructura
│   │   └── .env.example                # Plantilla de credenciales seguras
│   ├── core/                           # Núcleo algorítmico y matemático
│   │   ├── ads/                        # Ciclo de vida de anuncios (SAPI Binance)
│   │   ├── liquidity/                  # Tracking de saldo ARS y crypto en tiempo real
│   │   ├── network/                    # Clientes asíncronos resilientes (SAPI / Spot)
│   │   ├── pricing/                    # Reposicionadores de compra, venta y anti-colisión
│   │   ├── antiban_validator.py        # Cooldowns y límites de rate-limiting (Anti-ban)
│   │   ├── fiwind_client.py            # Oráculo de cotización para arbitraje de rescate
│   │   ├── market_scanner.py           # Escáner asíncrono concurrente con semáforos
│   │   ├── profit_tracker.py           # Contabilidad WAC e inventario compartido
│   │   ├── sell_advisor.py             # Agrupamiento de métodos en 3 clusters de venta
│   │   ├── sell_guardrails.py          # Auditoría de Break-Even, pisos y colchones
│   │   └── war_detector.py             # Detección y enfriamiento ante guerras de precios
│   ├── data/                           # Capa de Persistencia SQLite
│   │   ├── repos/                      # Repositorios desacoplados por entidad
│   │   ├── database.py                 # Pool y transacciones seguras
│   │   ├── models.py                   # Dataclasses inmutables de dominio
│   │   └── schema.py                   # DDL SQLite e índices optimizados
│   └── telegram_bot/                   # Interfaz de telemetría y control remoto
├── tests/                              # Suite de 210 pruebas unitarias deterministas
├── INICIAR_BOT_ORIGINAL.bat            # Script de arranque directo del Bot Original (Producción)
├── INICIAR_MODO_DEMO.bat               # Lanzador 1-Click interactivo con Modo Demo y Tests
├── main.py                             # Loop principal de ejecución
├── launcher.py                         # Menú CLI interactivo
├── tray_app.py                         # Monitor de bandeja de sistema (Windows Tray)
└── requirements.txt                    # Dependencias pip
```

---

## Modos de Ejecución

### 1. Modo Demo Zero-API (Recomendado para evaluadores y recruiters)
Ejecuta la microestructura completa del motor P2P en memoria sin requerir saldo ni credenciales de Binance:
```bash
python scripts/run_demo_showcase.py
# O simplemente doble clic en INICIAR_MODO_DEMO.bat y presionar Enter
```

### 2. Ejecución de la Suite de Pruebas Unitarias (Pytest)
Suite completa de 210 pruebas deterministas y 100% offline:
```bash
python -m pytest tests -v
# O vía INICIAR_MODO_DEMO.bat opción [5]
```

### 3. Ejecución en Producción / Paper
```bash
python main.py
# O interfaz visual en bandeja del sistema:
python tray_app.py
```

---

## Políticas de Seguridad & Alpha Protection
- **Zero Hardcoded Secrets:** Sin API keys en el código fuente. Se utiliza `.env.example` y resolución dinámica de variables de entorno.
- **Alpha Sanitization:** Parámetros propietarios de trading (deltas exactos, umbrales de competencia y pisos de volumen) han sido sanitizados o calibrados con valores demostrativos para proteger la propiedad intelectual de la estrategia comercial.
- **Sanitización de Datos:** Bases de datos de producción con datos operativos reales han sido eliminadas y reemplazadas por esquemas en memoria / sintéticos para las pruebas.
