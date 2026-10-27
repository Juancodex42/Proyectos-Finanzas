"""
Configuración centralizada y parámetros de estrategia del bot P2P Binance ARS.
Valores académicos/demo parametrizables vía variables de entorno (.env) o Telegram.
Referencia de diseño: docs/ARQUITECTURA.md
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Cargar .env desde la raíz del proyecto o desde src/config/
_project_root = Path(__file__).resolve().parent.parent.parent
_env_path = _project_root / ".env"
if not _env_path.exists():
    _env_path = _project_root / "src" / "config" / ".env"
load_dotenv(_env_path)

# ── API Keys ──────────────────────────────────────────────────────────
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
BINANCE_SECRET_KEY = os.getenv("BINANCE_SECRET_KEY", "") or os.getenv("BINANCE_API_SECRET", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
_raw_admin_ids = os.getenv("TELEGRAM_ADMIN_IDS", os.getenv("TELEGRAM_AUTHORIZED_USERS", TELEGRAM_CHAT_ID))
TELEGRAM_ADMIN_IDS = {
    int(x.strip())
    for x in _raw_admin_ids.split(",")
    if x.strip().lstrip("-").isdigit()
}

# ── Binance URLs ──────────────────────────────────────────────────────
BINANCE_BASE_URL = "https://api.binance.com"
BINANCE_SAPI_BASE = f"{BINANCE_BASE_URL}/sapi/v1"
BINANCE_API_BASE = f"{BINANCE_BASE_URL}/api/v3"

# ── Constantes de Trading ─────────────────────────────────────────────
# ── Alpha Sanitization (Configuración Académica / Demo) ───────────────
# Los activos de nicho ilíquidos y los umbrales propietarios de producción
# han sido parametrizados con valores académicos estándar de portafolio.
FIAT = "ARS"
STABLECOINS = {"USDT", "USDC", "DAI", "FDUSD", "TUSD"}

# 10 Criptomonedas estándar de alta capitalización habilitadas en Binance P2P ARS
P2P_ASSETS_ARS = [
    "USDT", "BTC", "ETH", "USDC", "BNB", "SOL",
    "XRP", "ADA", "DOGE", "FDUSD",
]

# Activos sin anuncios de venta en P2P ARS (criterio sell-less: superar con paso mínimo y respetar margen)
SELL_LESS_ASSETS = {"FDUSD"}
SELL_LESS_MIN_GAP = 0.01           # Paso mínimo para superar al competidor ($0.01 ARS)
SELL_LESS_MAX_MARKUP_PCT = 0.02    # 2% máximo sobre paridad spot para protección de compra

# Ratio de piso mínimo de precio creíble por activo (Guardarraíl anti-error 187031)
ASSET_MIN_PRICE_RATIOS = {
    "FDUSD": 0.90,
}
DEFAULT_MIN_PRICE_RATIO = 0.90

# Margen mínimo porcentual para Altcoins volátiles (BTC, ETH, SOL, BNB, etc.)
# 0.0 = Desactivado (las altcoins compiten con config.margin_min al igual que las estables)
ALTCOIN_MIN_MARGIN_PCT = 0.0

# Filtro de calidad de competidores para evitar perseguir anuncios cebo o fraudulentos
MIN_COMPETITOR_COMPLETION_RATE = 0.88  # Mínimo 88% de órdenes finalizadas
MIN_COMPETITOR_ORDERS = 15             # Mínimo 15 órdenes históricas
COMPETE_ONLY_MERCHANTS = True          # True = Compite exclusivamente contra comerciantes verificados (ignora usuarios comunes)
DEFAULT_BUY_AUTO_REPLY = "Buenas, no transfiero a terceros"
DEFAULT_BUY_REMARKS = "Buenas, no transfiero a terceros"
DEFAULT_SELL_AUTO_REPLY = "Buenas, solo transferencias del titular verificado en Binance. Rechazo pagos de terceros."
DEFAULT_SELL_REMARKS = "Buenas, solo transferencias del titular verificado en Binance. Rechazo pagos de terceros."
SELL_TAKER_ADDITIONAL_KYC_REQUIRED = 0       # 0 = Deshabilitado (sin cartel de [Verificación] en anuncios de venta)
SELL_BUYER_REG_DAYS_LIMIT = 90               # Exige mínimo 90 días de registro del comprador
SELL_USER_ALL_TRADE_COUNT_MIN = 100          # Exige mínimo 100 trades completados históricos
SELL_BUYER_BTC_POSITION_LIMIT = 0            # 0 = Deshabilitado (sin requisito de tenencia de BTC)

# Método ancla de mayor liquidez por grupo (referencia de precio para evitar distorsiones)
GROUP_ANCHOR_METHODS = {
    1: "MercadoPagoNew",
    2: "SantanderArgentina",
    3: "personalpay",
}

# Métodos de referencia de alta liquidez para anclaje de benchmark de salida (precio más bajo y seguro de venta)
LIQUID_REFERENCE_METHODS = [
    "MercadoPagoNew",
    "LemonCash",
    "BancoBrubankNew",
    "UalaNew",
    "NaranjaX",
    "SantanderArgentina",
]

# Configuración por defecto para creación de anuncios por activo
ASSET_DEFAULTS = {
    "USDT": {"init_amount": 100.0, "min_trans": 10000.0, "max_trans": 500000.0},
    "USDC": {"init_amount": 100.0, "min_trans": 10000.0, "max_trans": 500000.0},
    "FDUSD": {"init_amount": 100.0, "min_trans": 10000.0, "max_trans": 500000.0},
    "BTC": {"init_amount": 0.002, "min_trans": 10000.0, "max_trans": 500000.0},
    "ETH": {"init_amount": 0.05, "min_trans": 10000.0, "max_trans": 500000.0},
    "BNB": {"init_amount": 0.2, "min_trans": 10000.0, "max_trans": 500000.0},
    "SOL": {"init_amount": 1.0, "min_trans": 10000.0, "max_trans": 500000.0},
    "XRP": {"init_amount": 100.0, "min_trans": 10000.0, "max_trans": 500000.0},
    "ADA": {"init_amount": 500.0, "min_trans": 10000.0, "max_trans": 500000.0},
    "DOGE": {"init_amount": 1500.0, "min_trans": 10000.0, "max_trans": 500000.0},
}

# Precisión decimal permitida por activo en Binance P2P para initAmount
ASSET_PRECISION = {
    "USDT": 2,
    "USDC": 2,
    "FDUSD": 2,
    "BTC": 6,
    "ETH": 4,
    "BNB": 3,
    "SOL": 2,
    "XRP": 1,
    "ADA": 1,
    "DOGE": 1,
    "1000CHEEMS": 0,
}

# ── Defaults configurables via Telegram ───────────────────────────────
DEFAULT_MARGIN_MIN = 10.0          # ARS mínimo de diferencia con benchmark (Colchón de Compra)
DEFAULT_SELL_MARGIN_MIN = 5.0      # ARS mínimo de ganancia neta sobre WAC (Piso de Venta)
DEFAULT_PRICE_STEP = 0.01          # Incremento mínimo de precio
DEFAULT_POLL_INTERVAL = 30         # Segundos entre ciclos de polling
DEFAULT_VOLUME_REF = 500_000.0     # ARS, volumen de referencia para benchmark
DEFAULT_BALANCE_ARS = 0.0          # Saldo inicial ARS
LIQUIDITY_BUFFER = 1.0             # Buffer de seguridad desactivado (opera con el 100% real del saldo)

# ── Reporte Diario ────────────────────────────────────────────────────
DAILY_REPORT_HOUR = int(os.getenv("DAILY_REPORT_HOUR") or "23")      # Hora de envío del reporte diario (0-23)
DAILY_REPORT_MINUTE = int(os.getenv("DAILY_REPORT_MINUTE") or "55")  # Minuto de envío (0-59)

# ── Límites de Binance P2P ────────────────────────────────────────────
MAX_ADS_PER_ASSET = 3              # Máximo 3 anuncios por activo
MAX_METHODS_PER_AD = 5             # Máximo 5 métodos de pago por anuncio
MAX_TOTAL_METHODS = MAX_ADS_PER_ASSET * MAX_METHODS_PER_AD  # 15
AD_CREATION_COOLDOWN_SECONDS = 15.0 # Pausa entre creaciones de anuncios para evitar error 187000 (Binance SAPI exige >= 10-15s)
MIN_AD_PRICE_DIFF_RATIO = 0.0015   # 0.15% separación mínima en LATAM/ARS (FAQ 360043895111 Regla 5.1.3 exige >= 0.1%)
PASSIVE_UPDATE_COOLDOWN_SECONDS = 120.0  # Cooldown para ajustes pasivos (Spot/límites) cuando NO te superó un competidor P2P
PASSIVE_PRICE_HYSTERESIS_PCT = 0.0015    # 0.15% variación mínima en ajustes pasivos de Spot para evitar Error 83714
AD_API_ERROR_COOLDOWN_SECONDS = 600.0    # 600s (10 min) de circuit-breaker sobre un anuncio si Binance rechaza con 187031/187055
GROUP_INIT_MULTIPLIERS = {1: 1.00, 2: 0.985, 3: 0.975}  # Escalonamiento de initAmount entre G1, G2, G3 (Regla 5.1)
GROUP_MIN_MULTIPLIERS = {1: 1.0, 2: 1.15, 3: 1.30}     # Multiplicador del piso mínimo por grupo
GROUP_LIMIT_FACTORS = {                                # (min_factor, max_factor) con escalonamiento de $10.000 entre grupos
    1: (0.45, 0.99),
    2: (0.60, 0.98),
    3: (0.50, 0.97),
}

# Grupos oficiales de 5 métodos de pago (15 métodos en total)
PAYMENT_METHOD_GROUPS = {
    1: ["MercadoPagoNew", "LemonCash", "NaranjaX", "Beloapp", "UalaNew"],
    2: ["SantanderArgentina", "bancogalicia", "BankArgentina", "BancoBrubankNew", "Reba"],
    3: ["personalpay", "Prex", "Fiwind", "bnaplus", "BancoDelSol"],
}

# ── Scanner y Detección de Anomalías ──────────────────────────────────
TOP_N_BENCHMARK = 10               # Top N para calcular promedio benchmark
SEARCH_ROWS = 20                   # Anuncios por búsqueda
REGROUP_INTERVAL_HOURS = 6         # Re-evaluar agrupamiento cada X horas
COMPETITOR_ANOMALY_GAP_PCT = 0.01  # Brecha > 1% entre #1 y #2 = anomalía
SCANNER_CONCURRENCY = 12           # Concurrencia de escaneo paralelo con semáforo (10 a 12 recomendado)

# ── Guerra de precios y Seguridad ────────────────────────────────────
WAR_ESCALATION_THRESHOLD = 3       # Subidas consecutivas = guerra
WAR_ESCALATION_WINDOW_SECONDS = 180.0  # Ventana máxima entre subidas para considerar guerra (3 min)
WAR_COOLDOWN_MINUTES = 5           # Esperar 5 min (300s) antes de volver a competir (sin exagerar)
WATCHDOG_TIMEOUT_SECONDS = 300     # 5 minutos sin conexión = alerta y pausa preventiva

# ── Fiwind & Arbitraje de Rescate (Parámetros Demo Sanitizados) ──────
CRIPTOYA_FIWIND_URL = "https://criptoya.com/api/fiwind/usdt/ars"
FIWIND_RESCUE_MARGIN = 10.0         # ARS/USDT de ganancia mínima garantizada contra Fiwind en rescate
FIWIND_OPPORTUNITY_MARGIN = 10.0     # ARS/USDT de ganancia mínima para alertar arbitraje opcional con liquidez
FIWIND_CACHE_SECONDS = 30           # Segundos de caché para cotización Fiwind
FIWIND_ESTIMATED_TRANSFER_FEE_ARS = 400.0  # Costo operativo/fee fija estimada por transferencia
DEFAULT_USDT_BENCHMARK_FALLBACK = 1580.0   # TC fallback si no hay benchmark disponible
DEFAULT_BINANCE_SELL_TC_FALLBACK = 1610.0  # TC fallback venta en Binance si no hay datos recientes

# ── Headers HTTP para Binance SAPI ────────────────────────────────────
CLIENT_TYPE = "web"

# ── Base de datos ─────────────────────────────────────────────────────
DB_PATH = _project_root / "src" / "data" / "p2p_bot.db"

# ── Ad Status codes ───────────────────────────────────────────────────
AD_STATUS_ONLINE = 1
AD_STATUS_OFFLINE = 3
AD_STATUS_CLOSED = 4

# ── Configuración de Ventas P2P (3 Clusters / Anuncios) ───────────────
SELL_MIN_MARGIN_PCT = 0.002            # 0.2% ganancia mínima sobre costo ponderado de compra WAC
SELL_MAX_USDT_PER_AD = 500.0           # Tranche máximo de seguridad en USDT por anuncio
SELL_AUTO_EXECUTION = True             # True = Automático (reactiva y actualiza ventas en Binance); False = Semi-Automático
SELL_TICKET_COMPETITION_ENABLED = True  # Filtrar competidores por tamaño de ticket
SELL_ORACLE_MAX_DEV_PCT = 0.03         # Máximo desvío permitido (3%) vs Oráculo Fiwind Bid
SELL_MAX_STALE_DATA_SECONDS = 240.0    # Máxima antigüedad permitida de datos de benchmark (4 min)
SELL_STRATEGY_BY_CLUSTER = {
    1: "TOP_1",      # Billeteras: Puesto #1 (Top 1 verificado - 0.01 ARS)
    2: "LADDER_2",   # Bancos: Base + 2 * separación (+1.00 ARS)
    3: "LADDER_1",   # Fintechs: Base + 1 * separación (+0.50 ARS)
}
SELL_GROUP_INIT_MULTIPLIERS = {1: 1.00, 2: 0.985, 3: 0.975}
SELL_GROUP_LIMIT_FACTORS = {
    1: (0.50, 1.00),
    2: (0.50, 1.00),
    3: (0.50, 1.00),
}
SELL_AUTO_REPOSITION_ENABLED = True         # True = Full-Auto en el loop principal
SELL_MIN_PRICE_CHANGE_TRIGGER = 0.05        # $0.05 ARS histéresis anti-spam
SELL_MIN_STOCK_CHANGE_TRIGGER = 10.0        # 10 USDT cambio mínimo de stock para refrescar anuncio
SELL_MIN_USDT_THRESHOLD = 10.0              # Saldo mínimo de USDT para operar venta en Binance P2P
SELL_GROUP_FLOORS_ARS = {1: 20000.0, 2: 50000.0, 3: 30000.0}

# ── Estrategia Book-Aware (Calibración por Profundidad de Libro) ───────
SELL_PRICING_MODE = "BOOK_AWARE"            # "BOOK_AWARE" (dinámico por libro) o "FIXED_DELTA" (legacy)
SELL_PODIUM_TARGET = 1                      # Apuntar al puesto #1 en Billeteras
SELL_MIN_STEP_BEHIND = 0.01                 # Margen para posicionarse debajo de P2 ($0.01 ARS)
SELL_MAX_SPREAD_FROM_TOP1_PCT = 0.025       # Cap máximo de 2.5% sobre Top 1 para evitar saltos en libros vacíos
SELL_MIN_DELTA_BY_CLUSTER = {               # Delta mínimo de seguridad sobre Top 1 si P1 == P2 o libro comprimido
    1: 0.20,
    2: 0.50,
    3: 1.00,
}

# ── Escalera y Anti-Colisión de Ventas P2P (Opción A) ────────────────
# Separación fija en ARS entre anuncios de venta G1 -> G2 -> G3.
# Binance exige > $0.15 ARS (Error 187055 rango [X-0.15, X+0.15]).
SELL_AD_PRICE_DIFF_ARS = 0.35       # $0.35 ARS de separación fija entre peldaños de venta (> $0.15 ARS Error 187055)
SELL_CASCADE_MODE = "HIGH_ROTATION_LADDER"  # "HIGH_ROTATION_LADDER" (Opción A: G1 Puesto #1, G3 Base+$0.35, G2 Base+$0.70), "SPREAD_FIRST" (legacy invertido), o "MARKET_INDEPENDENT"


