"""
Suite de validación unitaria de la capa de dominio y correcciones de lógica contable.
Verifica normalización de huso horario, FIFO puro, desempate y deduplicación segura.
Referencia de diseño: docs/contratos_io_transacciones.md
"""

import pytest
from datetime import datetime, timezone
import pandas as pd
import sqlite3

from domain.models import Transaction, Lot, CostAssignment, InventoryGap
from domain.operations import OperationType, get_operation_priority
from domain.fifo_engine import compute_fifo_lots
from domain.tax_engine import calculate_cedular_tax, calculate_iibb_tax
from parsers.base_parser import parse_date


def test_timezone_naive_art_converted_to_utc():
    """Valida que fechas sin huso horario en exchanges argentinos se desplacen +3 horas a UTC."""
    # Ripio emite fecha local naive
    parsed = parse_date("2024-03-01 12:00:00", "Ripio Trade")
    assert parsed is not None
    # 12:00 ART debe ser 15:00 UTC
    assert parsed.hour == 15
    assert parsed.day == 1
    assert parsed.year == 2024

    # Fecha con 'Z' explícito se respeta
    parsed_utc = parse_date("2024-03-01 15:00:00Z", "Binance Spot")
    assert parsed_utc is not None
    assert parsed_utc.hour == 15


def test_op_priority_single_source_of_truth():
    """Valida que get_operation_priority establezca el orden Buy(1) > Out(2) > In(3) > Fee(4) > Sell(5)."""
    p_buy = get_operation_priority("Compra", monto_compra=100.0, monto_venta=0.0)
    p_out = get_operation_priority("Retiro", monto_compra=0.0, monto_venta=50.0)
    p_in = get_operation_priority("Depósito", monto_compra=50.0, monto_venta=0.0)
    p_fee = get_operation_priority("Fee de Red", monto_compra=0.0, monto_venta=1.0)
    p_sell = get_operation_priority("Venta", monto_compra=0.0, monto_venta=100.0)

    assert p_buy == 1
    assert p_out == 2
    assert p_in == 3
    assert p_fee == 4
    assert p_sell == 5

    # Términos alternativos de exchanges locales
    p_alt_in = get_operation_priority("Transferencia entrante", monto_compra=10.0, monto_venta=0.0)
    assert p_alt_in == 3


def test_domain_fifo_engine_pure_calculation():
    """Valida que compute_fifo_lots calcule costos e idempotencia sin requerir base de datos."""
    tx1 = Transaction(
        tx_hash="hash_buy_1",
        fecha=datetime(2024, 1, 10, 10, 0, 0),
        exchange="Binance Spot",
        exchange_root="BINANCE",
        tipo_operacion="Compra",
        moneda="USDT",
        monto_compra_cripto=100.0,
        cotizacion_compra=1000.0,
        monto_ars=100000.0
    )
    tx2 = Transaction(
        tx_hash="hash_sell_1",
        fecha=datetime(2024, 1, 15, 12, 0, 0),
        exchange="Binance Spot",
        exchange_root="BINANCE",
        tipo_operacion="Venta",
        moneda="USDT",
        monto_venta_cripto=40.0,
        cotizacion_venta=1200.0,
        monto_ars=48000.0
    )

    costs, gaps = compute_fifo_lots([tx1, tx2])
    assert len(costs) == 1
    assert len(gaps) == 0

    cost = costs[0]
    assert cost.tx_hash == "hash_sell_1"
    assert cost.cantidad_vendida == 40.0
    assert cost.costo_unitario_ars == 1000.0
    assert cost.costo_total_ars == 40000.0
    assert cost.monto_descubierto == 0.0

    # Idempotencia: una segunda corrida con el mismo input genera exactamente lo mismo
    costs2, gaps2 = compute_fifo_lots([tx1, tx2])
    assert costs == costs2
    assert gaps == gaps2


def test_domain_tax_engine():
    """Valida la fórmula del Régimen Cedular e Ingresos Brutos sin efectos secundarios."""
    res = calculate_cedular_tax(
        ventas_totales_ars=1000000.0,
        costo_base_fifo_ars=600000.0,
        gastos_deducibles_ars=50000.0,
        deduccion_especial_ars=100000.0,
        alicuota=0.15
    )
    # Resultado Bruto = 1.000.000 - 600.000 = 400.000
    # Renta Neta = 400.000 - 50.000 = 350.000
    # Base Imponible = 350.000 - 100.000 = 250.000
    # Impuesto = 250.000 * 0.15 = 37.500
    assert res["resultado_bruto_ars"] == 400000.0
    assert res["renta_neta_ars"] == 350000.0
    assert res["base_imponible_ars"] == 250000.0
    assert res["impuesto_determinado_ars"] == 37500.0

    iibb = calculate_iibb_tax(ingresos_brutos_ars=1000000.0, alicuota=0.03)
    assert iibb["impuesto_iibb_ars"] == 30000.0


def test_scoped_prune_auto_corrections():
    """Valida que prune_obsolete_auto_corrections con rango de fechas no borre correcciones históricas."""
    import tempfile, os
    from services.reconciliation_service import ReconciliationEngine

    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("""
            CREATE TABLE transactions (
                id INTEGER PRIMARY KEY,
                fecha TEXT, exchange TEXT, tipo_operacion TEXT, moneda TEXT,
                monto_compra_cripto REAL, monto_venta_cripto REAL, comentarios TEXT,
                is_certified INTEGER DEFAULT 0
            )
        """)
        c.execute("INSERT INTO transactions VALUES (1, '2023-05-01 12:00:00', 'Sistema de Conciliación', 'Ingreso Automático', 'USDT', 50.0, 0.0, 'para subsanar venta', 0)")
        c.execute("INSERT INTO transactions VALUES (2, '2024-06-01 12:00:00', 'Sistema de Conciliación', 'Ingreso Automático', 'USDT', 30.0, 0.0, 'para subsanar venta', 0)")
        conn.commit()
        conn.close()

        engine = ReconciliationEngine(db_path=db_path)
        engine.prune_obsolete_auto_corrections(coins=['USDT'], start_date='2024-01-01', end_date='2024-12-31')

        conn2 = sqlite3.connect(db_path)
        remaining = conn2.execute("SELECT id, fecha FROM transactions").fetchall()
        conn2.close()

        assert len(remaining) == 1
        assert remaining[0][0] == 1  # Sobrevivió el ID 1 (2023)
    finally:
        if os.path.exists(db_path):
            try:
                os.remove(db_path)
            except Exception:
                pass
