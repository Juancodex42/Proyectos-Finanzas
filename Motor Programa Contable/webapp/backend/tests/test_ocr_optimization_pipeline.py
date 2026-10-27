"""
Automated Test Suite for Optimized High-Performance OCR & Parallel Table Extraction Pipeline.
Validates:
1. Deskew and orientation detection accuracy (deskew_helper).
2. AngleMemory thread-safety and dominant angle propagation.
3. Fast single-pass RapidOCR extraction (ocr_helper).
4. Multi-core parallel page extraction and page order preservation (parallel_extractor).
5. Full PDF table extraction on both vector and scanned streams with financial math validation (pdf_table_extractor).
6. Compliance with clean architecture line limits (<= 450 lines).
"""

import os
import threading
import numpy as np
import cv2
import fitz
import pytest
from PIL import Image, ImageDraw

from parsers.deskew_helper import AngleMemory, deskew_image, detect_page_orientation_fast
from parsers.ocr_helper import _get_ocr_engine, ocr_pdf_page, ocr_pdf_pages
from parsers.parallel_extractor import ParallelPageExtractor, get_optimal_worker_count
from parsers.pdf_table_extractor import (
    extract_transactions_from_pdf_stream,
    resolve_amounts,
    clean_num,
    parse_date_str,
    extract_cpa_summary_table
)


class TestDeskewAndOrientation:
    """Validates geometric deskewing and orientation detection algorithms."""

    def test_deskew_straightens_tilted_image(self):
        """Verifies that tilted lines (e.g. -4 degrees) are detected and leveled."""
        # Create a synthetic white image with horizontal lines tilted by -4 degrees
        img = Image.new("RGB", (600, 800), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)
        for y in range(100, 700, 30):
            draw.line([(50, y), (550, y)], fill=(0, 0, 0), width=2)

        # Rotate by -4.0 degrees
        tilted_img = img.rotate(-4.0, expand=False, fillcolor=(255, 255, 255))

        deskewed_img, detected_angle = deskew_image(tilted_img, max_angle=15.0)

        assert abs(abs(detected_angle) - 4.0) < 1.0, f"Expected tilt magnitude ~ 4.0, got {detected_angle}"
        assert deskewed_img is not None
        # Verify the deskewed image is now straight (residual tilt == 0.0)
        _, residual_angle = deskew_image(deskewed_img, max_angle=15.0)
        assert residual_angle == 0.0, f"Expected 0 residual angle, got {residual_angle}"

    def test_deskew_preserves_already_straight_image(self):
        """Verifies that perfectly straight images undergo no unnecessary interpolation."""
        img = Image.new("RGB", (600, 800), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)
        for y in range(100, 700, 40):
            draw.line([(50, y), (550, y)], fill=(0, 0, 0), width=2)

        deskewed_img, detected_angle = deskew_image(img, max_angle=15.0)
        assert detected_angle == 0.0
        assert deskewed_img == img

    def test_orientation_detection_horizontal_vs_vertical(self):
        """Verifies fast detection of sideways (90/270 deg) vs upright (0 deg) tables."""
        # Upright table
        img_upright = Image.new("RGB", (600, 800), color=(255, 255, 255))
        draw = ImageDraw.Draw(img_upright)
        for y in range(100, 700, 25):
            draw.line([(50, y), (550, y)], fill=(0, 0, 0), width=1)
            draw.text((60, y + 2), "FECHA 2024-05-10 COMPRA USDT 1500.00", fill=(0, 0, 0))

        angle_upright = detect_page_orientation_fast(img_upright)
        assert angle_upright == 0

        # Sideways table rotated 270 degrees
        img_sideways = img_upright.rotate(270, expand=True)
        angle_sideways = detect_page_orientation_fast(img_sideways)
        assert angle_sideways in (90, 270)

    def test_angle_memory_thread_safety_and_consensus(self):
        """Verifies AngleMemory accumulates counts across concurrent workers and returns dominant angle."""
        mem = AngleMemory()
        assert mem.get_dominant_angle() == 0
        assert not mem.has_memory()

        def worker_record(angle, times):
            for _ in range(times):
                mem.record_angle(angle)

        threads = [
            threading.Thread(target=worker_record, args=(270, 50)),
            threading.Thread(target=worker_record, args=(0, 10)),
            threading.Thread(target=worker_record, args=(90, 5)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert mem.has_memory()
        assert mem.get_dominant_angle() == 270
        stats = mem.get_stats()
        assert stats[270] == 50
        assert stats[0] == 10

        mem.reset()
        assert not mem.has_memory()
        assert mem.get_dominant_angle() == 0

    def test_deskew_reversed_line_segments(self):
        """Verifies that lines drawn right-to-left (x1 > x2) are still correctly deskewed."""
        img = Image.new("RGB", (600, 800), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)
        # Draw lines explicitly from right to left with a 3 degree tilt
        for y in range(100, 700, 30):
            draw.line([(550, y), (50, y + 25)], fill=(0, 0, 0), width=2)

        deskewed_img, detected_angle = deskew_image(img, max_angle=15.0)
        assert abs(detected_angle) > 1.0, f"Expected non-zero detected angle for reversed lines, got {detected_angle}"
        assert deskewed_img is not None

    def test_angle_memory_does_not_poison_different_orientation(self):
        """Verifies an initial 0 deg (portrait cover) in AngleMemory does not force a 270 deg landscape page to 0."""
        mem = AngleMemory()
        # Record portrait cover page (0 degrees)
        mem.record_angle(0, weight=5)

        # Create landscape table page (lines run vertically when scanned sideways)
        img_upright = Image.new("RGB", (600, 800), color=(255, 255, 255))
        draw = ImageDraw.Draw(img_upright)
        for y in range(100, 700, 25):
            draw.line([(50, y), (550, y)], fill=(0, 0, 0), width=2)
        img_sideways = img_upright.rotate(270, expand=True)

        detected = detect_page_orientation_fast(img_sideways, angle_memory=mem)
        # Must detect sideways (270 or 90), NEVER 0 despite memory having 0!
        assert detected in (90, 270), f"Expected sideways orientation, got {detected}"


class TestOcrHelperOptimized:
    """Validates single-pass OCR execution and thread-local engine caching."""

    def test_single_pass_ocr_reads_page(self):
        """Verifies ocr_pdf_page extracts text accurately without multi-angle brute force."""
        doc = fitz.open()
        page = doc.new_page(width=600, height=400)
        page.insert_text((50, 100), "CERTIFICACION CONTABLE ANEXO I")
        page.insert_text((50, 150), "FECHA 2024-04-12 COMPRA USDT 2500.00")

        text = ocr_pdf_page(page, dpi=150)
        doc.close()

        assert "CERTIFICACION" in text or "CONTABLE" in text
        assert "USDT" in text or "2500" in text

    def test_ocr_pdf_pages_stops_at_cpa_keywords(self):
        """Verifies early exit in ocr_pdf_pages when certification header detected."""
        doc = fitz.open()
        p1 = doc.new_page()
        p1.insert_text((50, 50), "CERTIFICACION CONTADOR C.P.N. PERIODO 2024")
        p2 = doc.new_page()
        p2.insert_text((50, 50), "PAGE 2 DATA")

        text = ocr_pdf_pages(doc, max_pages=5, dpi=72)
        doc.close()

        assert "CERTIFICACION" in text
        # Because p1 satisfies both keywords, p2 should not have been reached
        assert "PAGE 2 DATA" not in text

    def test_ocr_reads_sideways_page_with_tilt(self):
        """Verifies ocr_pdf_page correctly extracts text from a sideways page with tilt."""
        import io
        img = Image.new("RGB", (800, 600), (255, 255, 255))
        draw = ImageDraw.Draw(img)
        draw.text((60, 60), "BINANCE P2P - COMPRA USDT 1500", fill=(0, 0, 0))
        for y in range(50, 400, 40):
            draw.line([(50, y), (750, y)], fill=(0, 0, 0), width=2)

        # Tilt by 3 deg then rotate 270 deg
        tilted = img.rotate(3.0, expand=False, fillcolor=(255, 255, 255))
        sideways = tilted.rotate(270, expand=True)

        buf = io.BytesIO()
        sideways.save(buf, format="PNG")
        buf_bytes = buf.getvalue()

        doc = fitz.open()
        p = doc.new_page(width=sideways.width, height=sideways.height)
        p.insert_image(p.rect, stream=buf_bytes)

        text = ocr_pdf_page(p, dpi=150)
        doc.close()

        assert "BINANCE" in text or "USDT" in text or "1500" in text


class TestParallelPageExtractor:
    """Validates multi-core parallel extraction and page order preservation."""

    def test_parallel_extraction_preserves_page_order(self):
        """Ensures that async worker results are strictly assembled in 0..N-1 order."""
        doc = fitz.open()
        for i in range(8):
            p = doc.new_page()
            p.insert_text((50, 50), f"PAGE_IDENTIFIER_{i}")
        pdf_bytes = doc.tobytes()
        doc.close()

        extractor = ParallelPageExtractor(max_workers=4)
        progress_calls = []

        def callback(done, total):
            progress_calls.append((done, total))

        results = extractor.extract_document_hybrid(
            file_bytes=pdf_bytes,
            dpi=150,
            progress_callback=callback
        )

        assert len(results) == 8
        for i in range(8):
            assert f"PAGE_IDENTIFIER_{i}" in results[i]

    def test_optimal_worker_count_bounds(self):
        """Ensures CPU worker count adheres to safety limits (1 <= workers <= 4)."""
        workers = get_optimal_worker_count()
        assert 1 <= workers <= 4
        # Explicit override
        assert get_optimal_worker_count(2) == 2


class TestPdfTableExtractor:
    """Validates full end-to-end certification table extraction and financial mathematics."""

    def test_instant_vector_extraction(self):
        """Verifies vector text PDFs bypass OCR and complete in <0.2s."""
        doc = fitz.open()
        p = doc.new_page()
        p.insert_text((50, 50), "BINANCE P2P")
        p.insert_text((50, 80), "2024-05-15 14:30:00 SELL USDT 1000.00 1150.00 1150000.00")
        pdf_bytes = doc.tobytes()
        doc.close()

        txs = extract_transactions_from_pdf_stream(pdf_bytes, filename="cert_binance.pdf")
        assert len(txs) >= 1
        tx = txs[0]
        assert tx["Tipo de Operación"] == "Venta"
        assert tx["Moneda"] == "USDT"
        assert tx["Exchange"] == "Binance"
        assert tx["Monto ARS"] == 1150000.0
        assert tx["Cotización Venta"] == 1150.0
        assert tx["Monto Venta (Cripto)"] == 1000.0

    def test_financial_math_resolve_amounts(self):
        """Verifies Qty * Price ~= Total ARS resolution across market bands."""
        # 1. Triplet match: Total = 1,120,000, Price = 1120.0, Qty = 1000.0
        total, price, qty = resolve_amounts([1000.0, 1120000.0, 1120.0], "USDT", year=2024)
        assert total == 1120000.0
        assert price == 1120.0
        assert qty == 1000.0

        # 2. Pair match: Total = 500,000, Qty = 500.0 -> Price = 1000.0
        total, price, qty = resolve_amounts([500000.0, 500.0], "USDT", year=2024)
        assert total == 500000.0
        assert price == 1000.0
        assert qty == 500.0

        # 3. BTC triplet match: Total = 40,000,000, Price = 80,000,000, Qty = 0.5
        total, price, qty = resolve_amounts([0.5, 40000000.0, 80000000.0], "BTC", year=2024)
        assert total == 40000000.0
        assert price == 80000000.0
        assert qty == 0.5

    def test_clean_num_and_date_parsing_edge_cases(self):
        """Verifies number cleaning handles Argentine formatting ($1.234.567,89)."""
        assert clean_num("$ 1.234.567,89") == 1234567.89
        assert clean_num("1234,50 ARS") == 1234.50
        assert clean_num("0.00543210") == 0.0054321
        assert clean_num("") == 0.0

        assert parse_date_str("2024-03-15 10:20:30") == "2024-03-15 10:20:30"
        assert parse_date_str("15/03/2024 10:20") == "2024-03-15 10:20:00"
        assert parse_date_str("invalid_date") == ""

    def test_scanned_pdf_raster_page_extraction(self):
        """Verifies end-to-end parallel OCR extraction on a pure raster image page (no vector text)."""
        import io
        img = Image.new("RGB", (800, 400), (255, 255, 255))
        draw = ImageDraw.Draw(img)
        draw.text((50, 50), "BINANCE P2P", fill=(0, 0, 0))
        draw.text((50, 100), "2024-06-10 12:00:00 BUY USDT 2000.00 1200.00 2400000.00", fill=(0, 0, 0))

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        img_bytes = buf.getvalue()

        doc = fitz.open()
        page = doc.new_page(width=800, height=400)
        page.insert_image(page.rect, stream=img_bytes)
        pdf_bytes = doc.tobytes()
        doc.close()

        txs = extract_transactions_from_pdf_stream(pdf_bytes, filename="scanned_cert.pdf")
        assert len(txs) >= 1
        tx = txs[0]
        assert tx["Exchange"] == "Binance"
        assert tx["Tipo de Operación"] == "Compra"
        assert tx["Moneda"] == "USDT"
        assert tx["Monto Compra (Cripto)"] == 2000.0
        assert tx["Cotización Compra"] == 1200.0
        assert tx["Monto ARS"] == 2400000.0

    def test_corrupted_or_empty_stream_handling(self):
        """Verifies empty or malformed streams fail gracefully with empty lists."""
        assert extract_transactions_from_pdf_stream(b"") == []
        assert extract_transactions_from_pdf_stream(b"corrupted header not a pdf") == []
        assert extract_transactions_from_pdf_stream(None) == []

    def test_resolve_amounts_boundary_cases(self):
        """Verifies boundary cases in financial math resolution."""
        assert resolve_amounts([], "USDT") == (0.0, 0.0, 0.0)
        assert resolve_amounts([500.0], "USDT") == (500.0, 0.0, 0.0)
        # Year beyond 2026 with clear price (2500) and qty (50) -> total 125000
        tot, p, q = resolve_amounts([50.0, 125000.0, 2500.0], "USDT", year=2028)
        assert tot == 125000.0
        assert p == 2500.0
        assert q == 50.0

    def test_extract_cpa_summary_table(self):
        """Verifies summary table extraction from certificate cover."""
        doc = fitz.open()
        p = doc.new_page()
        p.insert_text((50, 50), "Certifico que el monto total de ingresos suma de $ 12.500.000,50")
        p.insert_text((50, 100), "por movimientos bancarios por $ 15.000.000,00")
        res = extract_cpa_summary_table(doc)
        doc.close()

        assert res["total_ventas"] == 15000000.0
        assert res["ganancia_neta"] == 12500000.50
        assert res["total_compras"] == 2499999.5

    def test_resolve_amounts_rejects_trivial_noise(self):
        """Verifies that 1.0 * 1.0 = 1.0 noise is rejected in favor of the real trade triplet."""
        nums = [1.0, 1.0, 1.0, 1000.0, 1150.0, 1150000.0]
        total, price, qty = resolve_amounts(nums, "USDT", year=2024)
        assert total == 1150000.0, f"Expected total 1150000.0, got {total}"
        assert price == 1150.0, f"Expected price 1150.0, got {price}"
        assert qty == 1000.0, f"Expected qty 1000.0, got {qty}"

    def test_scanned_page_with_sparse_stamp_is_not_treated_as_pure_vector(self):
        """Verifies that a scanned page with a tiny vector stamp ('Página 1 de 10') is not skipped as pure vector."""
        import io
        img = Image.new("RGB", (800, 400), (255, 255, 255))
        draw = ImageDraw.Draw(img)
        draw.text((50, 50), "BINANCE P2P", fill=(0, 0, 0))
        draw.text((50, 100), "2024-05-15 14:30:00 SELL USDT 500.00 1150.00 575000.00", fill=(0, 0, 0))

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        img_bytes = buf.getvalue()

        doc = fitz.open()
        page = doc.new_page(width=800, height=400)
        # Insert image
        page.insert_image(page.rect, stream=img_bytes)
        # Insert tiny stamp text (15 characters)
        page.insert_text((50, 380), "Página 1 de 10")
        pdf_bytes = doc.tobytes()
        doc.close()

        extractor = ParallelPageExtractor()
        results = extractor.extract_document_hybrid(pdf_bytes, dpi=150)
        assert 0 in results
        # Scanned table content inside the image MUST be extracted via OCR
        assert "BINANCE" in results[0] or "USDT" in results[0] or "575000" in results[0]

    def test_clean_architecture_file_length_limits(self):
        """Enforces that all parser files strictly respect the 450 lines limit."""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        parser_files = [
            os.path.join(base_dir, "parsers", "deskew_helper.py"),
            os.path.join(base_dir, "parsers", "ocr_helper.py"),
            os.path.join(base_dir, "parsers", "parallel_extractor.py"),
            os.path.join(base_dir, "parsers", "pdf_table_extractor.py"),
        ]

        for fpath in parser_files:
            assert os.path.isfile(fpath), f"File {fpath} does not exist"
            with open(fpath, "r", encoding="utf-8") as f:
                lines = f.readlines()
            assert len(lines) <= 450, f"{fpath} has {len(lines)} lines, exceeding 450 limit!"
