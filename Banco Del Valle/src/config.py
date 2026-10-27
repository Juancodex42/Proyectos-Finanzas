"""
Módulo de configuración global y parámetros regulatorios BCRA / UIF.
Define rutas del sistema, constantes de liquidez, encajes, tasas base y seguridad.
Referencia de diseño: docs/normativa_encajes_bcra.md
"""

from pathlib import Path
import os

# ----------------------------------------------------------------------------
# Rutas del Sistema
# ----------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
DATABASE_DIR = BASE_DIR / "database"
DB_PATH = os.getenv("BANCO_DB_PATH", str(DATABASE_DIR / "banco_scoring.db"))
SCHEMA_PATH = str(DATABASE_DIR / "schema.sql")

# ----------------------------------------------------------------------------
# Parámetros Regulatorios BCRA y Tesorería
# ----------------------------------------------------------------------------
ENCAJE_FLEXIBLE_PCT: float = 0.30       # 30% encaje legal para cajas de ahorro/sueldo
ENCAJE_PLAZO_FIJO_PCT: float = 0.12     # 12% encaje legal para plazos fijos a 30 días
COLCHON_LIQUIDEZ_SEGURIDAD: float = 5_000_000.0  # $5.000.000 colchón de seguridad
CAPITAL_PATRIMONIO_INICIAL: float = 50_000_000.0 # $50.000.000 patrimonio neto inicial

# ----------------------------------------------------------------------------
# Parámetros de Tasas Nominales Anuales (TNA) Base
# ----------------------------------------------------------------------------
TNA_FLEXIBLE_BASE: float = 0.285        # 28.5% TNA rendimiento diario flexible
TNA_PLAZO_FIJO_BASE: float = 0.38       # 38% TNA base para depósitos a término
TNA_PRESTAMO_PERSONAL_BASE: float = 0.60 # 60% TNA base crédito personal

# ----------------------------------------------------------------------------
# Parámetros Compliance y Antifraude (UIF)
# ----------------------------------------------------------------------------
SMVM_BASE: float = 300_000.0            # Salario Mínimo Vital y Móvil de referencia
UMBRAL_AML_SMVM_FACTOR: int = 40        # 40 SMVM = $12.000.000 ARS umbral EBR
DIAS_RFI_DESCARGO: int = 30             # 30 días hábiles para justificar fondos

# ----------------------------------------------------------------------------
# Ratios Crediticios Máximos
# ----------------------------------------------------------------------------
RATIO_CUOTA_INGRESO_MAX: float = 0.35   # 35% máx afectación sueldo particulares
RATIO_CUOTA_VENTAS_MAX: float = 0.20    # 20% máx afectación ventas PyMEs

# ----------------------------------------------------------------------------
# Seguridad y Autenticación
# ----------------------------------------------------------------------------
JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "banco_del_valle_catamarca_secure_key_2026_xyz")
JWT_ALGORITHM: str = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8 horas
MAX_LOGIN_ATTEMPTS: int = 5
LOCKOUT_MINUTES: int = 15
