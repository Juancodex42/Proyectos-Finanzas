# 📖 Documentación Técnica Integral — Bot P2P Binance ARS

> **Documento de Arquitectura, Ingeniería de Software y Especificación Funcional.**  
> Este documento detalla la estructura completa de carpetas, módulos, funciones, justificación arquitectónica de dependencias (`imports`), gestión de riesgos y buenas prácticas operacionales del sistema.

---

## 📑 Tabla de Contenidos

1. [Visión General del Sistema](#1-visión-general-del-sistema)
2. [Estructura de Carpetas y Responsabilidades](#2-estructura-de-carpetas-y-responsabilidades)
3. [Módulos y Funciones Detallados por Áreas](#3-módulos-y-funciones-detallados-por-áreas)
   - [Área 1: Orquestación, Concurrencia y Ciclo de Vida](#área-1-orquestación-concurrencia-y-ciclo-de-vida)
   - [Área 2: Conectividad Externa y Clientes de Red](#área-2-conectividad-externa-y-clientes-de-red)
   - [Área 3: Análisis de Mercado y Reposicionamiento](#área-3-análisis-de-mercado-y-reposicionamiento)
   - [Área 4: Gestión de Anuncios y Ciclo Operativo](#área-4-gestión-de-anuncios-y-ciclo-operativo)
   - [Área 5: Gestión de Riesgo, Liquidez y Anti-Baneo](#área-5-gestión-de-riesgo-liquidez-y-anti-baneo)
   - [Área 6: Persistencia Transaccional y Modelos](#área-6-persistencia-transaccional-y-modelos)
   - [Área 7: GUI de Escritorio y Bandeja del Sistema](#área-7-gui-de-escritorio-y-bandeja-del-sistema)
   - [Área 8: Telemetría y Control Remoto (Telegram C2)](#área-8-telemetría-y-control-remoto-telegram-c2)
   - [Área 9: Herramientas Operacionales y Diagnóstico](#área-9-herramientas-operacionales-y-diagnóstico)
4. [Análisis de Dependencias e Imports (Qué usa, en dónde y por qué)](#4-análisis-de-dependencias-e-imports)
5. [Buenas Prácticas sobre Logs en Producción](#5-buenas-prácticas-sobre-logs-en-producción)
6. [Auditoría y Organización de Tests](#6-auditoría-y-organización-de-tests)

---

## 1. Visión General del Sistema

El **Bot P2P Binance ARS** es una plataforma institucional de **Market Making Algorítmico y Arbitraje Cruzado** para el mercado de persona a persona (P2P) de Binance en Pesos Argentinos (ARS). 

El sistema resuelve la necesidad de proveer liquidez bidireccional continua (comprar y vender criptoactivos) maximizando el diferencial de precios (*spread*) mientras mantiene un riesgo de inventario controlado, protege la cuenta contra penalizaciones y baneos de Binance, y permite al operador supervisar y alterar el comportamiento mediante interfaces de escritorio y Telegram.

### Parámetros Principales de Operación
- **Mercado Base**: Binance P2P C2C (Fiat: `ARS`).
- **Criptomonedas Soportadas**: 14 activos (`USDT`, `BTC`, `ETH`, `USDC`, `BNB`, `SOL`, `XRP`, `ADA`, `DOGE`, `WLD`, `TRUMP`, `1000CHEEMS`, `FDUSD`, `U`).
- **Métodos de Pago**: 15 canales bancarios y billeteras virtuales de Argentina organizados en 3 clusters estratégicos.
- **Concurrencia**: Escaneo de mercado no bloqueante con semáforos asíncronos (`asyncio` + `aiohttp`).
- **Persistencia**: SQLite con modo `WAL` (*Write-Ahead Logging*) y compresión histórica periódica.

---

## 2. Estructura de Carpetas y Responsabilidades

| Carpeta / Archivo | Rol en el Ecosistema | Propósito y Contenido |
|---|---|---|
| `config/` | Configuración Global | Centraliza la lectura de variables de entorno (`.env`), constantes operacionales de trading, multiplicadores de grupo, timeouts, márgenes por defecto y definición de activos. |
| `core/` | Motor de Negocio (Core) | Contiene la lógica analítica y operativa: clientes HTTP autenticados, escáneres de libro de órdenes, algoritmos de pricing, validadores de riesgo, detector de guerras de precios y componentes GUI. |
| `data/` | Almacenamiento y Estado | Capa de persistencia: base de datos SQLite (`database.py`) con soporte WAL transaccional y definición de modelos de dominio fuertemente tipados con Dataclasses (`models.py`). |
| `logs/` | Registro de Eventos | Carpeta aislada (incorporada a `.gitignore`) destinada a alojar los archivos rotativos de trazas del sistema (`bot.log`, `bot.log.1`, etc.). |
| `manuales_api/` | Documentación de Exchange | Documentación técnica oficial provista por Binance en PDF (*Binance C2C SAPI v7.4 Manual* y especificación WebSocket). |
| `scratch/` | Espacio de Experimentación | Archivos temporales de análisis, volcados de respuestas JSON de anuncios, scripts de prueba ad-hoc y notas de investigación de mercado. No intervienen en la ejecución de producción. |
| `scripts/` | Herramientas Operacionales | Scripts auxiliares ejecutables para tareas de mantenimiento: verificación de conectividad (`verify_connection.py`), compactación de BD (`compact_db.py`), benchmarks (`benchmark_parallel_scan.py`) y simulaciones. |
| `strategies/` | Optimización Estratégica | Módulos de optimización y análisis predictivo basados en el histórico de trades (`optimizer.py`). |
| `telegram_bot/` | Telemetría y C2 | Servidor de bot de Telegram interactivo con teclados en línea (*Inline Keyboards*), dashboards actualizables en vivo y formateadores de mensajes en Markdown v1/v2. |
| `tests/` | Calidad y Regresión | Suite completa de más de 20 archivos de pruebas automatizadas (`pytest` / `unittest`) que validan el comportamiento unitario, concurrencia y parches críticos con simulación (*mocking*). |
| Archivos raíz | Bootstrap y Orquestación | Contiene el lanzador desacoplado (`launcher.py`), el daemon de bandeja (`tray_app.py`), el orquestador del loop (`main.py`) y los ejecutables por lotes (`INICIAR_BOT_ORIGINAL.bat` e `INICIAR_MODO_DEMO.bat`). |

---

## 3. Módulos y Funciones Detallados por Áreas

### Área 1: Orquestación, Concurrencia y Ciclo de Vida

#### `launcher.py`
Lanzador interactivo para la consola de Windows que garantiza un arranque desacoplado del proceso principal.
- `is_already_running() -> bool`: Verifica si el daemon ya se encuentra activo intentando una conexión TCP local al puerto de bloqueo `PORT_LOCK` (29170). Si responde, envía la señal `SHOW` para traer el visor de logs al frente.
- `get_pythonw_path() -> str`: Detecta la presencia del binario `pythonw.exe` en el entorno virtual activo para lanzar procesos en segundo plano sin asociar una consola CMD huérfana.
- `stream_logs_until_init(...) -> bool`: Lee y emite en tiempo real en la consola las líneas iniciales de `bot.log` hasta que el motor notifica *"Inicialización completa"* o *"Modo Standby"*, informando al usuario que ya puede cerrar la ventana de consola sin detener el bot.
- `tail_live_logs(log_path)`: Bucle de lectura continua tipo `tail -f` que mantiene la emisión de logs mientras la ventana permanezca abierta.

#### `tray_app.py`
Punto de entrada del daemon en segundo plano. Integra la aplicación en la bandeja del sistema de Windows, maneja la ventana gráfica de logs y orquesta el hilo de `asyncio`.
- `prevent_windows_sleep()`: Invoca la API Win32 `kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)` para bloquear el modo de suspensión de Windows y la hibernación de la placa de red durante la noche.
- `restore_windows_sleep()`: Restablece las políticas normales de ahorro de energía del sistema operativo al apagarse el bot.
- `TrayApplication`:
  - `__init__(start_visible: bool)`: Inicializa la raíz de Tkinter (oculta por defecto), crea la instancia del motor `BotEngine`, e inicializa los sockets locales.
  - `start()`: Inicia el hilo de fondo (`engine_thread`) donde corre el loop de `asyncio` del bot, arranca el listener de sockets IPC para comandos locales y lanza el icono de bandeja con `pystray`.
  - `_ipc_listen()`: Escucha conexiones en `localhost:29170`. Permite comandos como `SHOW` (abrir visor de logs) o `QUIT` (apagado ordenado).
  - `shutdown()`: Orquesta la finalización segura: pausa los anuncios, cierra el loop de `asyncio`, destruye el icono de bandeja y restaura la política de suspensión del OS.

#### `main.py`
Orquestador maestro que coordina los módulos de negocio en un bucle continuo de eventos.
- `BotEngine`:
  - `__init__()`: Instancia la base de datos, clientes HTTP (`BinanceClient`, `SpotClient`, `FiwindClient`), escáneres, gestores de anuncios y trackers.
  - `initialize()`: Sincroniza la hora con Binance, descarga el listado de métodos de pago configurados por el usuario, reconcilia anuncios existentes en la base de datos y arranca el bot de Telegram.
  - `run_cycle()` / `_run_cycle_unlocked()`: Ejecuta una iteración completa del motor:
    1. Escaneo simultáneo de libros de órdenes de compra y venta.
    2. Sincronización de balances de la cuenta y órdenes completadas.
    3. Evaluación de arbitrajes de rescate contra Fiwind.
    4. Cálculo de reposicionamiento de anuncios de compra (`Repositioner`).
    5. Cálculo de reposicionamiento de anuncios de venta con algoritmo en escalera (`SellRepositioner`).
    6. Auditoría estricta anti-baneo (`AntiBanValidator`).
    7. Ejecución de mutaciones de precio y límites hacia la API de Binance.
    8. Persistencia de snapshots y actualización del dashboard en Telegram.
  - `turn_on()` / `turn_off()`: Métodos atómicos para activar la colocación de anuncios o pausarlos todos (modo Standby).
  - `calibrate_all_ads()`: Recalcula y publica inmediatamente los límites y precios óptimos de todos los anuncios en base al libro actual.
  - `audit_market_dry_run()`: Ejecuta un escaneo y cálculo completo en memoria sin emitir ninguna llamada de modificación hacia Binance, retornando un reporte diagnóstico de cómo se posicionaría el bot.
  - `shutdown()`: Cierra conexiones a bases de datos, cancela tareas pendientes y asegura que ningún anuncio quede desatendido.

#### `config/settings.py`
Fuente única de la verdad de configuración técnica y financiera:
- Carga variables de `.env` vía `python-dotenv`.
- Define multiplicadores de escalonamiento de anuncios (`GROUP_INIT_MULTIPLIERS`, `GROUP_LIMIT_FACTORS`).
- Establece listas oficiales de 14 activos P2P y asignación de los 15 métodos de pago en 3 grupos (`PAYMENT_METHOD_GROUPS`).
- Fija constantes anti-baneo: `MIN_AD_PRICE_DIFF_RATIO = 0.0015` (0.15%), `PASSIVE_UPDATE_COOLDOWN_SECONDS = 120.0`, `AD_CREATION_COOLDOWN_SECONDS = 15.0`.

---

### Área 2: Conectividad Externa y Clientes de Red

#### `core/binance_client.py`
Cliente HTTP asíncrono para la API de Comerciantes C2C/P2P de Binance (SAPI v7.4).
- `validate_credentials()`: Valida localmente la integridad de API Key y Secret Key.
- `sync_time()`: Consulta `/api/v3/time` para calcular el desfase de reloj local respecto al servidor de Binance (`_time_offset`), evitando errores de firma `recvWindow`.
- `_sign(params: dict) -> str`: Genera firmas criptográficas HMAC-SHA256 con codificación URL segura.
- `_request(...)`: Envuelve todas las llamadas HTTP en `aiohttp.ClientSession`. Rastrea el consumo de cuota de IP (`X-SAPI-USED-IP-WEIGHT-1M`), gestiona códigos de error nativos (como `187000`, `187055`, `83714`) e implementa reintentos con *backoff*.
- Métodos de Negocio:
  - `search_ads(...)`: Consulta pública/privada de la cartelera P2P para un activo, fiat, método de pago y tipo (`BUY`/`SELL`).
  - `list_my_ads(...)`: Lista los anuncios propios activos o pausados del comerciante.
  - `create_ad(...)` / `update_ad(...)`: Mutación de precios, montos mínimos/máximos y métodos de pago.
  - `update_ad_status(...)`: Conmutación rápida entre estados `ONLINE` (1) y `OFFLINE` (3).
  - `get_funding_asset(...)`: Consulta el balance real en la billetera de fondos (Funding Wallet).
  - `get_my_payment_methods()`: Recupera los métodos de pago registrados en la cuenta con sus respectivos IDs internos.

#### `core/spot_client.py`
Cliente HTTP ligero y sin autenticación para consultar la API pública de Spot de Binance (`/api/v3`).
- `get_price(symbol: str) -> float`: Obtiene el precio de mercado instantáneo de un par Spot (ej. `BTCUSDT`).
- `get_usdt_prices(assets: list[str]) -> dict[str, float]`: Consulta por lotes la paridad respecto a USDT de múltiples altcoins para arbitraje de conversión.
- `get_24hr_volatilities(assets: list[str]) -> dict[str, float]`: Calcula la variación porcentual de las últimas 24 horas para adaptar márgenes en activos volátiles.

#### `core/fiwind_client.py`
Cliente de oráculo externo para el broker argentino Fiwind a través de la API pública de CriptoYa.
- `get_quotes() -> tuple[float, float]`: Obtiene las puntas de compra (`bid`) y venta (`ask`) de USDT en Pesos Argentinos con un sistema de caché asíncrona de 30 segundos.
- `get_usdt_bid() -> float`: Retorna el precio al cual Fiwind compra USDT, utilizado como piso de rescate y oráculo de control de cordura (*sanity check*).

---

### Área 3: Análisis de Mercado y Reposicionamiento

#### `core/market_scanner.py`
Motor de escaneo y benchmarking de alta velocidad.
- `scan_competitors(...)`: Escanea la cartelera P2P para un activo y método de pago específico. Aplica filtros de calidad descartando competidores con menos de 88% de efectividad o pocas órdenes, e ignorando comerciantes no verificados si `COMPETE_ONLY_MERCHANTS` está activo.
- `scan_usdt_benchmark(...)`: Calcula el precio promedio ponderado de los 10 mejores competidores en métodos de alta liquidez para establecer el precio de referencia (*Benchmark*).
- `scan_full_cycle(...)`: Coordina el escaneo de todos los activos habilitados utilizando un semáforo de concurrencia (`SCANNER_CONCURRENCY = 12`) para maximizar la velocidad de recolección de datos.

#### `core/method_selector.py`
Algoritmo de clustering dinámico de métodos de pago.
- `get_available_methods()`: Cruza los métodos configurados en Binance con las definiciones del sistema.
- `score_method(...)`: Califica cada método de pago según el volumen de operaciones, spread promedio y velocidad de rotación.
- `select_and_group(...)`: Agrupa los 15 métodos de pago en 3 grupos balanceados para los 3 anuncios permitidos por activo.

#### `core/repositioner.py`
Cerebro de precios para anuncios de **COMPRA** (Maker Buy / El bot adquiere cripto).
- `evaluate_ad(...)`: Analiza la posición relativa de un anuncio propio frente a la cartelera. Determina si el bot está primero, superado o si el competidor líder presenta una anomalía de precio (*gap* desproporcionado).
- `resolve_asset_price_collisions(...)`: Garantiza que los anuncios G1, G2 y G3 del mismo activo mantengan una separación matemática mínima de al menos `0.15%` (`MIN_AD_PRICE_DIFF_RATIO`), impidiendo que Binance rechace la actualización por precios duplicados.
- `execute_repositioning(...)`: Valida con `AntiBanValidator` y aplica las órdenes de cambio de precio hacia Binance.

#### `core/sell_repositioner.py`
Motor de reposicionamiento para anuncios de **VENTA** (Maker Sell / El bot liquida cripto a usuarios).
- Implementa el algoritmo **"Opción A - High Rotation Ladder"**:
  - **G1 (Billeteras virtuales masivas)**: Se sitúa agresivamente en el puesto #1 del podio (`Top 1 - $0.01 ARS`) para maximizar rotación.
  - **G3 (Fintechs)**: Se posiciona en `Precio Base + $0.35 ARS`.
  - **G2 (Bancos tradicionales)**: Se posiciona en `Precio Base + $0.70 ARS`.
- `resolve_sell_collisions(...)`: Asegura una distancia fija superior a $0.15 ARS entre los tres anuncios de venta para evitar taxativamente el `Error 187055`.
- `execute_sell_decisions(...)`: Aplica las decisiones de precio en Binance de forma transaccional.

#### `core/sell_advisor.py`
Módulo asesor de precios de venta basado en la profundidad del libro de órdenes (*Book-Aware Pricing*).
- `calculate_book_aware_sell_price(...)`: Si el libro de órdenes está comprimido o vacío, calcula el delta óptimo respecto al Top 1 para no regalar margen ni quedar fuera de mercado.
- `get_sell_advice(...)`: Asesora al motor de venta sobre el precio objetivo de cada cluster considerando el tamaño de ticket promedio.

#### `strategies/optimizer.py`
Analizador estadístico de performance.
- `analyze_method_performance()`: Evalúa qué métodos de pago generaron mayor volumen y ganancia neta en las últimas 24/48 horas.
- `suggest_margin_adjustment()`: Sugiere incrementos o reducciones en el colchón de margen en función de la velocidad de ejecución de órdenes.

---

### Área 4: Gestión de Anuncios y Ciclo Operativo

#### `core/ads_manager.py`
Maneja el ciclo de vida completo de los anuncios en Binance P2P.
- `sync_my_ads()` / `sync_my_sell_ads()`: Consulta Binance y sincroniza el estado local de todos los anuncios de compra y venta.
- `update_ad_params(...)` / `update_sell_ad_params(...)`: Actualiza precio, límites transaccionales (mínimo y máximo) y métodos de pago asignados.
- `pause_all()` / `resume_all()` / `pause_by_asset()` / `resume_by_asset()`: Control masivo de estados online/offline para paradas de emergencia o cambios de modo.
- `reconcile_all_ads()` / `reconcile_sell_ads()`: Verifica que cada activo tenga exactamente los 3 anuncios reglamentarios; si falta alguno, lo crea; si hay sobrantes, los pausa o cierra.
- `delete_all_buy_ads()` / `delete_all_sell_ads()`: Cierra definitivamente los anuncios en Binance para permitir una reconfiguración limpia desde cero.

---

### Área 5: Gestión de Riesgo, Liquidez y Anti-Baneo

#### `core/antiban_validator.py`
Guardián de reglas oficiales de Binance P2P (FAQ 360043895111).
- `audit_asset_decisions(decisions: list[RepositionDecision]) -> list[AntiBanViolation]`:
  - Verifica que ningún par de anuncios del mismo activo y tipo tenga una separación de precio inferior al `0.15%`.
  - Verifica que los montos iniciales (`initAmount`) respeten los escalonamientos obligatorios.
  - Comprueba que los límites mínimos y máximos en ARS no violen los rangos legales de la plataforma.
- `audit_all_cycle_decisions(...)`: Intercepta y frena en seco cualquier decisión que viole los términos antes de que se transmita por la red.

#### `core/sell_guardrails.py`
Capa de seguridad financiera para operaciones de venta.
- `validate_break_even(price, wac_cost, min_margin_pct)`: Impide vender por debajo del costo ponderado más el margen de beneficio mínimo.
- `validate_oracle_sanity(price, fiwind_bid, max_dev_pct)`: Comprueba que el precio calculado no se desvíe más del 3% respecto a la cotización de Fiwind.
- `validate_data_freshness(benchmark_timestamp, max_age_seconds)`: Rechaza reposicionamientos si los datos de mercado tienen más de 4 minutos de antigüedad.
- `audit_sell_price(...)`: Ejecuta la batería de validaciones anteriores y autoriza o veta la publicación del precio.

#### `core/war_detector.py`
Detector heurístico de guerras de precios destructivas (*Undercutting Wars*).
- `check_escalation(asset, method, new_price) -> bool`: Registra si un competidor superó nuestro precio más de 3 veces consecutivas (`WAR_ESCALATION_THRESHOLD = 3`) en una ventana de 3 minutos (`WAR_ESCALATION_WINDOW_SECONDS = 180`).
- Si detecta una guerra activa, coloca el anuncio en enfriamiento (*cooldown*) de 5 minutos, absteniéndose de perseguir al competidor hasta que el mercado se estabilice.

#### `core/liquidity_tracker.py`
Controlador del balance y compromisos de capital.
- `set_balance(amount_ars)`: Registra el saldo real en cuenta bancaria/billetera.
- `committed_balance`: Suma del capital actualmente bloqueado en órdenes P2P abiertas pendientes de liberación.
- `available_balance`: Saldo neto disponible para abrir nuevas operaciones (`balance - committed_balance`).
- `sync_orders()` / `sync_swaps()`: Detecta nuevas órdenes de compra y venta en Binance, actualizando el estado de capital de manera inmediata.

#### `core/profit_tracker.py`
Calculador de costo promedio ponderado y contabilidad analítica.
- `get_effective_wac_cost(asset) -> float`: Calcula el costo real por unidad adquirida en compras recientes.
- `calculate_profit(sell_price, wac_cost, volume) -> ProfitReport`: Determina la ganancia bruta, comisiones de exchange y ganancia neta en Pesos Argentinos.

---

### Área 6: Persistencia Transaccional y Modelos

#### `data/database.py`
Abstracción de acceso a datos sobre SQLite con arquitectura para alta concurrencia.
- `connect()`: Establece conexión aplicando pragmas de rendimiento:
  - `PRAGMA journal_mode=WAL;` (Lecturas concurrentes no bloqueadas por escrituras).
  - `PRAGMA synchronous=NORMAL;` (Rendimiento I/O optimizado manteniendo seguridad de disco).
  - `PRAGMA busy_timeout=15000;` (Manejo automático de esperas ante bloqueos temporales).
- `init_schema()`: Crea tablas para snapshots de mercado, benchmarks, anuncios propios, órdenes detectadas, cotizaciones de Fiwind, cambios de precios y configuración dinámica.
- `_execute_write(...)`: Ejecuta sentencias de escritura de forma atómica y sincronizada entre hilos mediante `threading.Lock`.
- `record_compact_market_intel(...)` / `get_market_hourly_summary(...)`: Métodos de agregación para destilación de métricas históricas.

#### `data/models.py`
Contratos de datos tipados mediante `@dataclass`:
- `AdInfo`: Representación estructurada de un anuncio de la cartelera P2P de Binance (precios, límites, métricas del comerciante).
- `MyAd`: Modelo de anuncio propio (número de anuncio, activo, tipo, precio actual, grupo, límites, estado).
- `Benchmark`: Instantánea del precio de referencia de mercado.
- `DetectedOrder`: Orden de compra o venta P2P registrada para tracking de saldo.
- `RepositionDecision` / `SellDecision`: Objeto de comando que encapsula una decisión de cambio de precio o estado lista para ser auditada y ejecutada.

---

### Área 7: GUI de Escritorio y Bandeja del Sistema

#### `core/tray_icon.py`
Controlador del System Tray en Windows mediante `pystray` y `Pillow`.
- `_build_menu()`: Construye el menú contextual de la bandeja:
  - Estado del motor (Activo / Standby / Pausado).
  - Abrir Visor de Logs.
  - Alternar Encendido / Apagado.
  - Reconciliar anuncios.
  - Salir limpiamente del sistema.
- `notify(title, message)`: Emite notificaciones emergentes nativas de Windows ante eventos críticos (desconexión, arbitraje detectado, ventas concluidas).

#### `core/log_viewer.py`
Ventana gráfica de consola en tiempo real construida con Tkinter.
- Estética terminal hacker (fondo negro `#0C1017`, texto verde consola `#00FF66`).
- Funcionalidades:
  - Auto-scroll automático conmutable mediante botón interactivo.
  - Pausa de buffer para inspección de líneas sin perder registros nuevos.
  - Botón directo para abrir `bot.log` en el Bloc de Notas de Windows.
  - Indicador de estado en vivo conmutado con el motor.

---

### Área 8: Telemetría y Control Remoto (Telegram C2)

#### `telegram_bot/bot.py`
Interfaz de comando y control remota construida sobre `python-telegram-bot v21+`.
- Seguridad: Autorización estricta mediante validación de `TELEGRAM_ADMIN_IDS`.
- Comandos y Paneles Táctiles:
  - `/start` / `/panel`: Despliega teclados en línea con botones para control operativo total.
  - `/power_on` / `/power_off`: Conmuta entre ejecución activa y modo reposo (*Standby*).
  - `/status`: Estado instantáneo de balances, anuncios online y alertas de salud.
  - `/reconcile`: Dispara la verificación y alineación de anuncios en Binance.
  - `/calibrate`: Ejecuta la recalibración instantánea de precios según la cartelera viva.
  - `/simulate`: Corre una simulación en vivo del motor durante 5 minutos reportando por chat.
  - `update_live_dashboard()`: Tarea en segundo plano que actualiza un mensaje fijado en Telegram con los precios, márgenes y spreads del mercado en tiempo real.

#### `telegram_bot/formatters.py`
Módulo de renderizado de texto para Telegram.
- `escape_md(text) -> str`: Escapa caracteres reservados de Markdown v1/v2 para prevenir fallos de parseo en la API de Telegram.
- `format_status(...)`: Formatea el resumen de estado del bot.
- `format_daily_report(...)`: Genera el reporte financiero diario consolidado con volumen operado, ganancias netas y métricas de rotación.
- `format_rescue_notification(...)`: Construye alertas de arbitraje urgente con Fiwind.

---

### Área 9: Herramientas Operacionales y Diagnóstico

#### `scripts/verify_connection.py`
Herramienta de diagnóstico y comprobación previa (*Smoke Test / Onboarding*).
- Verifica conectividad pública con Binance Spot.
- Comprueba autenticación y firma HMAC contra Binance SAPI P2P.
- Lista los anuncios propios y métodos de pago registrados.
- Envía un mensaje de prueba al chat de Telegram configurado.

#### `scripts/benchmark_parallel_scan.py`
Script de medición de rendimiento concurrente.
- Compara tiempos de respuesta entre escaneo secuencial y escaneo concurrente con semáforos asíncronos (`asyncio.Semaphore`).
- Mide el impacto en los encabezados de consumo de IP-weight de Binance.

#### `scripts/compact_db.py`
Mantenimiento de base de datos con técnica de destilación sin riesgo (*Zero-Risk Database Compaction*).
- Extrae agregaciones estadísticas de snapshots antiguos.
- Reconstruye una réplica limpia y compactada de `p2p_bot.db`.
- Aplica `VACUUM` y reemplaza la base en caliente preservando la integridad del historial analítico.

---

## 4. Análisis de Dependencias e Imports

A continuación se detalla **qué bibliotecas se importan en cada área del proyecto y la justificación técnica de su elección**:

### 1. Concurrencia y Red Asíncrona
- **`asyncio`** (`main.py`, `core/binance_client.py`, `core/market_scanner.py`, `telegram_bot/bot.py`):
  - *¿Por qué?* El trading P2P de alta frecuencia requiere consultar decenas de libros de órdenes y APIs simultáneamente sin bloquear el hilo de ejecución. `asyncio` provee el modelo de concurrencia cooperativa ideal para aplicaciones con alto I/O de red.
- **`aiohttp`** (`core/binance_client.py`, `core/spot_client.py`, `core/fiwind_client.py`):
  - *¿Por qué?* Es la librería asíncrona de cliente HTTP más rápida y robusta del ecosistema Python. Permite mantener sesiones persistentes (`ClientSession`) con reutilización de conexiones TCP (Keep-Alive), reduciendo la latencia de handshake SSL en cada consulta a Binance.
- **`asyncio.Semaphore`** (`core/market_scanner.py`, `scripts/benchmark_parallel_scan.py`):
  - *¿Por qué?* Limita el número de solicitudes HTTP concurrentes exactamente a 12 workers, impidiendo la saturación del ancho de banda y evitando sobrepasar el umbral de rate-limiting (HTTP 429) de Binance.

### 2. Seguridad y Criptografía
- **`hmac` y `hashlib`** (`core/binance_client.py`):
  - *¿Por qué?* La API privada de Binance (SAPI) exige que cada solicitud autenticada lleve una firma HMAC generada con el algoritmo SHA-256 utilizando la `SECRET_KEY` y los parámetros de la URL/Body serializados junto al timestamp en milisegundos.
- **`urllib.parse.urlencode`** (`core/binance_client.py`):
  - *¿Por qué?* Asegura la serialización canónica de los parámetros de consulta para que la cadena de firma coincida exactamente con la calculada en los servidores de Binance.

### 3. Persistencia y Gestión de Datos
- **`sqlite3`** (`data/database.py`):
  - *¿Por qué?* Motor de base de datos relacional embebido, de latencia ultrabaja (en memoria/disco local) y sin dependencias de servicios externos pesados (como PostgreSQL o MySQL). Al configurarse en modo WAL (*Write-Ahead Logging*), soporta múltiples lectores simultáneos sin bloquear a los escritores.
- **`dataclasses` (`dataclass`, `field`)** (`data/models.py`):
  - *¿Por qué?* Permite estructurar los datos del dominio con tipado estático, inmutabilidad opcional, validación y menor sobrecarga de memoria que los diccionarios tradicionales o clases estándar sin boilerplate.
- **`json`** (`data/database.py`, `core/binance_client.py`, `core/market_scanner.py`):
  - *¿Por qué?* Serialización y parseo de payloads enviados y recibidos por las APIs REST de Binance, y almacenamiento de métodos de pago y listas dinámicas en columnas de SQLite.

### 4. Integración con el Sistema Operativo (Windows & Daemon)
- **`socket`** (`launcher.py`, `tray_app.py`, `core/binance_client.py`):
  - *¿Por qué?* En `launcher.py` y `tray_app.py`, se utiliza un socket TCP local en `127.0.0.1:29170` como mecanismo de exclusión mutua (*Single-Instance Lock*) y canal de comunicación entre procesos (IPC) para asegurar que jamás corran dos instancias simultáneas del bot.
- **`ctypes`** (`tray_app.py`):
  - *¿Por qué?* Brinda acceso directo a la API nativa de Windows `kernel32.dll`. Permite llamar a `SetThreadExecutionState` para evitar que Windows active el modo reposo o desconecte la red en horas de la madrugada.
- **`subprocess`** (`launcher.py`):
  - *¿Por qué?* Permite a `launcher.py` invocar a `pythonw.exe` creando un nuevo grupo de procesos desacoplado (`DETACHED_PROCESS` | `CREATE_NEW_PROCESS_GROUP`), liberando la consola CMD.
- **`pathlib.Path`** (`main.py`, `config/settings.py`, `data/database.py`, etc.):
  - *¿Por qué?* Manejo multiplataforma y seguro de rutas de archivos relativas a la raíz del proyecto, evitando inconsistencias entre barras inclinadas en Windows y Linux.

### 5. Interfaz Gráfica y Telemetría
- **`pystray` y `PIL` (`Pillow`)** (`core/tray_icon.py`, `tray_app.py`):
  - *¿Por qué?* `pystray` proporciona integración nativa con la bandeja del sistema (System Tray) de Windows. `Pillow` se utiliza para dibujar y renderizar dinámicamente el icono del bot en memoria (con colores de estado: verde para activo, ámbar para standby, rojo para error).
- **`tkinter`** (`core/log_viewer.py`, `tray_app.py`):
  - *¿Por qué?* Librería GUI estándar integrada en Python que no requiere dependencias externas pesadas (a diferencia de PyQt o Electron). Ideal para el visor de logs con consola en tiempo real.
- **`python-telegram-bot` (`telegram`, `telegram.ext`)** (`telegram_bot/bot.py`):
  - *¿Por qué?* Framework asíncrono oficial y robusto para interactuar con la Bot API de Telegram, soportando polling asíncrono, teclados táctiles en línea y renderizado de texto enriquecido.

### 6. Logging y Configuración
- **`logging` y `RotatingFileHandler`** (`main.py`, `tray_app.py`):
  - *¿Por qué?* Gestión profesional de trazas de ejecución. `RotatingFileHandler` rota automáticamente los archivos de log al alcanzar 10 MB manteniendo un máximo de 5 copias de respaldo, evitando que el disco se llene. El parámetro `delay=True` impide bloqueos de archivo en Windows hasta que se emite la primera línea.
- **`dotenv` (`python-dotenv`)** (`config/settings.py`):
  - *¿Por qué?* Carga de variables de entorno desde archivos `.env`, separando credenciales y secretos del código fuente para evitar fugas en repositorios Git.

---

## 5. Buenas Prácticas sobre Logs en Producción

### Diagnóstico de la Situación Inicial
El proyecto contaba con 6 archivos de registro acumulados en la raíz (`bot.log`, `bot.log.1` ... `bot.log.5`) con un peso aproximado de 10 MB cada uno (totalizando ~61.5 MB).

### ¿Por qué mantener logs en la raíz es una mala práctica?
1. **Contaminación del Repositorio y Riesgo en Git**:
   - Presentar un proyecto para una postulación laboral con archivos de decenas de megabytes en el directorio raíz genera una impresión de desorden operativo.
   - Aunque estén en `.gitignore`, cualquier descuido (`git add -f`) puede versionar accidentalmente megabytes de trazas en el historial de Git de forma irreversible.
2. **Fuga de Información Sensible (Data Leakage)**:
   - Los logs en caliente registran nombres de usuario de contrapartes P2P, IDs de órdenes, balances bancarios e información de red.
3. **Bloqueos de Concurrencia en Windows (`WinError 32`)**:
   - En sistemas Windows, los archivos abiertos por un proceso con `RotatingFileHandler` quedan bloqueados a nivel de kernel. Si un script o usuario intenta moverlos o borrarlos mientras el bot opera, el sistema operativo genera una excepción `PermissionError: [WinError 32]`.

### Estándar de Buena Práctica Implementado
1. **Aislamiento en Carpeta `logs/`**:
   - Todos los archivos de log deben residir dentro del subdirectorio dedicado `logs/` (ej. `logs/bot.log`).
2. **Regla Global en `.gitignore`**:
   - Se añadió la regla explícita `logs/` en el archivo `.gitignore` para garantizar que ningún archivo generado en ese directorio sea rastreado por Git.
3. **Rotación y Retención**:
   - Tamaño máximo por archivo: **10 MB** (`maxBytes = 10 * 1024 * 1024`).
   - Copias de respaldo: **5 archivos** (`backupCount = 5`).
   - Apertura diferida: **`delay = True`** para que el manejador no bloquee descriptores de archivo hasta que se produzca la primera escritura.
4. **Centralización Definitiva en `logs/`**:
   - Se ha creado la carpeta `logs/` con `.gitkeep`, se han movido los archivos `bot.log` a `logs/bot.log` y se ha actualizado `LOG_FILE_PATH` en todos los puntos de entrada (`main.py`, `tray_app.py`, `launcher.py`, `core/tray_icon.py`).
   - `.gitignore` excluye `logs/*`, `*.log` y `bot.log*`.

---

## 6. Auditoría y Organización de Tests

### Diagnóstico de Pruebas en el Proyecto
El proyecto dispone de una carpeta formal `tests/` con **20 archivos de suite de pruebas unitarias y de integración** (**210 pruebas automatizadas con `pytest` y 100% de tasa de aprobación**) que verifican exhaustivamente cálculos de WAC, lógica de precios, parches de concurrencia, guardarraíles anti-baneo y modelos.

En el directorio raíz existían tres archivos con prefijo `test_`:
1. `test_connection.py`: Script de comprobación manual que prueba claves de API, Binance Spot, Binance SAPI y Telegram.
2. `test_parallel_scan.py`: Benchmark de velocidad que comparó el escaneo secuencial versus concurrente durante la fase de optimización.
3. `test_pdf_search.py`: Script utilitario puntual de 30 líneas que buscaba texto dentro de los manuales en PDF.

### Resolución Aplicada
Para mantener el estándar de la industria y presentar un repositorio impecable para postulación laboral:
- `test_pdf_search.py` fue archivado en `scratch/` por tratarse de un script de investigación prescindible en producción.
- `test_parallel_scan.py` fue adaptado y alojado profesionalmente en `scripts/benchmark_parallel_scan.py` con resolución de rutas desacoplada.
- `test_connection.py` fue transformado en `scripts/verify_connection.py`, funcionando como una herramienta de validación previa al despliegue (*Smoke Test / Healthcheck*).
- Se preservaron las rutas relativas mediante `PROJECT_ROOT = Path(__file__).resolve().parent.parent` y `sys.path.insert(0, str(PROJECT_ROOT))`, garantizando que ninguna importación se rompa independientemente de la carpeta desde la que se ejecuten.

---

> **Conclusión**: Esta arquitectura desacoplada, con tolerancia a fallos, cumplimiento estricto de normativas de exchange y gestión matemática de riesgos, representa un proyecto de ingeniería de software listo para producción y preparado para auditorías técnicas de alto nivel.
