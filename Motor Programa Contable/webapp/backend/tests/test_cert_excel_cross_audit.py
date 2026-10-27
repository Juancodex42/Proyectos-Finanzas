import pytest
from datetime import datetime
from services.cert_excel_cross_audit_service import audit_certification_vs_excel, resolve_cross_audit_discrepancy
from parsers.pdf_table_extractor import parse_date_str


def test_pdf_table_extractor_date_sanitization():
    # Test OCR misread digit recovery
    assert parse_date_str('2024-42-17 00:00:00') == '2024-12-17 00:00:00'
    assert parse_date_str('2024-92-17 00:00:00') == '2024-12-17 00:00:00'
    assert parse_date_str('2025-01-00 00:00:00') == '2025-01-01 00:00:00'
    assert parse_date_str('2025-02-41 00:00:00') == '2025-02-24 00:00:00'
    assert parse_date_str('2025-61-12 00:00:00') == '2025-01-12 00:00:00'


def test_cross_audit_execution():
    res = audit_certification_vs_excel()
    assert res["success"] is True
    assert "discrepancies" in res
    assert "summary" in res
    assert isinstance(res["summary"]["total_discrepancies"], int)


def test_cross_audit_resolve_action():
    res = resolve_cross_audit_discrepancy(tx_id=999999, action="dismiss")
    assert res["success"] is True
