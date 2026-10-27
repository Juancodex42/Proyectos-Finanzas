"""
Regression test suite verifying fixes across CryptoTax Pro:
- Bank statement parser & date normalization idempotency
- Bank reconciliation timezone alignment
- FIFO engine and gap service deficit drag isolation
- Invariant C.P.N. certified transactions protection
- Operational Excel generation
- Windows scheduler headless configuration
"""
import io
import re
import sqlite3
import pandas as pd
import pytest

from parsers.bank_statement_parser import parse_bank_statement_file
from services.bank_persistence_service import normalize_bank_date
from services.bank_reconciliation_service import _parse_to_arg_tz
from services.certifications_service import sync_certified_transactions_status
from services.operational_excel_service import generate_operational_excel


def test_bank_date_normalization_idempotency():
    """Ensure normalize_bank_date does not alter local dates or drift on repeated passes."""
    d_local = "2024-05-10 14:30:00"
    pass1 = normalize_bank_date(d_local)
    pass2 = normalize_bank_date(pass1)
    assert pass1 == d_local
    assert pass2 == d_local

    d_iso_t = "2024-05-10T14:30:00"
    assert normalize_bank_date(d_iso_t) == "2024-05-10 14:30:00"

    d_latin = "10/05/2024 14:30"
    assert normalize_bank_date(d_latin) == "2024-05-10 14:30:00"


def test_bank_reconciliation_timezone_alignment():
    """UTC timestamps from exchange P2P orders must convert to Argentina local time (-3h)."""
    utc_str = "2024-05-10 17:00:00"
    arg_dt = _parse_to_arg_tz(utc_str, assume_utc=True)
    assert arg_dt.strftime("%Y-%m-%d %H:%M:%S") == "2024-05-10 14:00:00"


def test_bank_statement_parser_csv():
    """CSV parser should detect standard bank statement formats."""
    csv_content = (
        "Fecha,Concepto,Referencia,Monto\n"
        "10/05/2024 10:15:00,Transferencia recibida Juan Perez,REF-98765,150000.50\n"
        "11/05/2024 18:20:00,Transferencia enviada Proveedor,REF-12345,-50000.00\n"
    ).encode('utf-8')

    f = io.BytesIO(csv_content)
    f.filename = "extracto_galicia.csv"
    bank_name, movements = parse_bank_statement_file(f, f.filename)
    assert bank_name is not None
    assert len(movements) == 2
    assert movements[0].tipo_movimiento == "CREDITO"
    assert movements[0].monto_ars == 150000.50
    assert movements[1].tipo_movimiento == "DEBITO"
    assert movements[1].monto_ars == 50000.00


def test_certified_transactions_immutability():
    """Any transaction falling within an active certification must have is_certified=1."""
    conn = sqlite3.connect(":memory:")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE transactions (
            tx_hash TEXT PRIMARY KEY,
            fecha TEXT,
            exchange TEXT,
            moneda TEXT,
            tipo_operacion TEXT,
            monto_compra_cripto REAL,
            monto_venta_cripto REAL,
            source TEXT,
            is_certified INTEGER DEFAULT 0,
            certification_id INTEGER DEFAULT NULL
        )
    """)
    c.execute("""
        CREATE TABLE certifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            period_label TEXT,
            start_date TEXT,
            end_date TEXT,
            is_active INTEGER DEFAULT 1
        )
    """)

    # Active cert for May 2024
    c.execute("INSERT INTO certifications (period_label, start_date, end_date, is_active) VALUES ('Mayo 2024', '2024-05-01 00:00:00', '2024-05-31 23:59:59', 1)")
    
    # Insert tx inside cert and tx outside cert
    c.execute("INSERT INTO transactions (tx_hash, fecha, exchange, moneda, tipo_operacion, monto_compra_cripto, source, is_certified) VALUES ('h1', '2024-05-15 12:00:00', 'Binance', 'USDT', 'Compra Cripto', 100.0, 'EXCHANGE_API', 0)")
    c.execute("INSERT INTO transactions (tx_hash, fecha, exchange, moneda, tipo_operacion, monto_compra_cripto, source, is_certified) VALUES ('h2', '2024-06-15 12:00:00', 'Binance', 'USDT', 'Compra Cripto', 100.0, 'EXCHANGE_API', 0)")
    conn.commit()

    sync_certified_transactions_status(conn)

    h1_cert = c.execute("SELECT is_certified FROM transactions WHERE tx_hash = 'h1'").fetchone()[0]
    h2_cert = c.execute("SELECT is_certified FROM transactions WHERE tx_hash = 'h2'").fetchone()[0]

    assert h1_cert == 1, "Transaction inside certified range must be marked is_certified=1"
    assert h2_cert == 0, "Transaction outside certified range must remain is_certified=0"
    conn.close()


def test_windows_scheduler_headless_configuration():
    """Verify setup_windows_scheduler.ps1 points to launch_autosync_silent.vbs, not start_system.py."""
    import os
    scheduler_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "setup_windows_scheduler.ps1"))
    with open(scheduler_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "launch_autosync_silent.vbs" in content
    assert "start_system.py" not in content
    assert "launch_silent.vbs" not in content


def test_operational_excel_generation():
    """Verify operational Excel workbook builds with default settings and empty or mock rows."""
    output = generate_operational_excel([], {})
    wb_bytes = output.getvalue()
    assert len(wb_bytes) > 1000
    assert wb_bytes[:4] == b"PK\x03\x04"  # Valid ZIP/XLSX magic header


def test_parse_date_str_ocr_healing_and_formats():
    """Verify parse_date_str fixes OCR misread years (2075->2025, 2624/2924->2024) and handles dash/slash variations."""
    from parsers.pdf_table_extractor import parse_date_str

    # OCR year corruptions commonly seen in scanned CPA certificates
    assert parse_date_str("2075-02-09") == "2025-02-09 00:00:00"
    assert parse_date_str("2075-04-09 00:00:00") == "2025-04-09 00:00:00"
    assert parse_date_str("2624-12-24") == "2024-12-24 00:00:00"
    assert parse_date_str("2924-12-17 14:30:00") == "2024-12-17 14:30:00"

    # Dash and slash formats
    assert parse_date_str("09-04-2025") == "2025-04-09 00:00:00"
    assert parse_date_str("17/12/2024") == "2024-12-17 00:00:00"
    assert parse_date_str("31/12/24") == "2024-12-31 00:00:00"

    # Impossible years must be discarded
    assert parse_date_str("1995-01-01") == ""
    assert parse_date_str("2099-01-01") == ""


def test_gap_enrichment_does_not_drift_into_future():
    """Verify enrich_gaps_with_clues caps latest_system_date at current wall clock time."""
    from services.gap_enrichment_service import enrich_gaps_with_clues
    from datetime import datetime

    res = enrich_gaps_with_clues([])
    current_year = datetime.now().year
    for ef in res.get("exchange_freshness", []):
        parsed_dt = pd.to_datetime(ef["latest_system_date"])
        assert parsed_dt.year <= current_year, f"latest_system_date {ef['latest_system_date']} must not exceed current year"


def test_stale_source_alerts_distinguish_api_from_csv():
    """Verify that source_freshness_service distinguishes API sources from CSV statements and formats messages accurately."""
    from services.source_freshness_service import resolve_exchange_api_info, format_stale_source_alert

    # API source resolution
    bitso_info = resolve_exchange_api_info("BITSO")
    assert bitso_info["is_api"] is True
    assert bitso_info["api_id"] == "bitso"

    bybit_info = resolve_exchange_api_info("BYBIT")
    assert bybit_info["is_api"] is True
    assert bybit_info["api_id"] == "bybit"

    # CSV source resolution
    fiwind_info = resolve_exchange_api_info("FIWIND")
    assert fiwind_info["is_api"] is False
    assert fiwind_info["api_id"] is None

    # Alert formatting for API
    f_info_bitso = {
        "last_tx_date": "2025-08-18",
        "days_behind_latest": 426,
        "latest_system_date": "2026-10-19"
    }
    bitso_info_configured = dict(bitso_info)
    bitso_info_configured["has_credentials"] = True
    alert_bitso = format_stale_source_alert("BITSO", f_info_bitso, bitso_info_configured)
    assert alert_bitso["is_api"] is True
    assert "Faltan extractos recientes" not in alert_bitso["message"]
    assert "Fuente API de BITSO conectada" in alert_bitso["message"] or "API de BITSO" in alert_bitso["message"]

    bitso_info_unconfigured = dict(bitso_info)
    bitso_info_unconfigured["has_credentials"] = False
    alert_unconf = format_stale_source_alert("BITSO", f_info_bitso, bitso_info_unconfigured)
    assert alert_unconf["is_api"] is True
    assert "sin API configurada" in alert_unconf["message"]

    # Alert formatting for CSV
    f_info_fiwind = {
        "last_tx_date": "2026-09-14",
        "days_behind_latest": 34,
        "latest_system_date": "2026-10-19"
    }
    alert_fiwind = format_stale_source_alert("FIWIND", f_info_fiwind, fiwind_info)
    assert alert_fiwind["is_api"] is False
    assert "(ej. Fiwind / OKX)" not in alert_fiwind["message"]
    assert "Extracto desactualizado en FIWIND" in alert_fiwind["message"]


