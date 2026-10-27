"""
Parallel multi-core document page OCR extractor using concurrent.futures.
Distributes scanned page processing across safe CPU worker pools while strictly
preserving page order and memory safety.
"""

import os
import fitz
import concurrent.futures
from typing import Dict, List, Optional, Callable

try:
    from .ocr_helper import ocr_pdf_page, _get_ocr_engine
    from .deskew_helper import AngleMemory
except ImportError:
    from parsers.ocr_helper import ocr_pdf_page, _get_ocr_engine
    from parsers.deskew_helper import AngleMemory


def get_optimal_worker_count(max_workers: Optional[int] = None) -> int:
    """
    Determines optimal worker thread count. On Windows, caps at min(cpu_count - 1, 4)
    to keep system UI and background tasks responsive.
    """
    if max_workers and max_workers > 0:
        return max_workers

    cpu_cnt = os.cpu_count() or 2
    # Leave at least 1 core for OS / UI / web server, max 4 workers
    return max(1, min(cpu_cnt - 1, 4))


def _process_single_page(
    page_idx: int,
    file_bytes: bytes,
    dpi: int,
    angle_memory: Optional[AngleMemory]
) -> tuple:
    """
    Worker function executed in worker thread.
    Opens its own isolated fitz document handle from RAM bytes to avoid lock contention.
    Guarantees document handle closure in finally block.
    """
    local_doc = None
    try:
        local_doc = fitz.open(stream=file_bytes, filetype="pdf")
        page = local_doc[page_idx]
        text = ocr_pdf_page(
            page,
            dpi=dpi,
            grayscale=False,
            engine=None,  # Thread-local engine in ocr_helper
            angle_memory=angle_memory
        )
        return page_idx, text
    except Exception as e:
        print(f"[PARALLEL OCR WORKER ERROR] Page {page_idx}: {e}")
        return page_idx, ""
    finally:
        if local_doc is not None:
            try:
                local_doc.close()
            except Exception:
                pass


class ParallelPageExtractor:
    """
    Coordinates multi-core OCR page extraction.
    Ensures thread isolation, shared AngleMemory propagation, and ordered output.
    """

    def __init__(self, max_workers: Optional[int] = None):
        self.max_workers = get_optimal_worker_count(max_workers)

    def extract_scanned_pages(
        self,
        file_bytes: bytes,
        page_indices: List[int],
        dpi: int = 150,
        angle_memory: Optional[AngleMemory] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Dict[int, str]:
        """
        Processes a specified list of scanned page indices concurrently.

        Args:
            file_bytes: Raw PDF bytes.
            page_indices: List of page numbers (0-indexed) requiring OCR.
            dpi: Pixmap render resolution (default 150 DPI).
            angle_memory: Optional shared AngleMemory instance.
            progress_callback: Optional callback receiving (completed, total).

        Returns:
            Dict[int, str]: Mapping of page_idx -> extracted_text.
        """
        if not page_indices or not file_bytes:
            return {}

        results: Dict[int, str] = {}
        total = len(page_indices)
        shared_memory = angle_memory if angle_memory is not None else AngleMemory()

        # For a single page, execute synchronously to avoid executor thread overhead
        if total == 1:
            p_idx = page_indices[0]
            _, text = _process_single_page(p_idx, file_bytes, dpi, shared_memory)
            results[p_idx] = text
            if progress_callback:
                try:
                    progress_callback(1, 1)
                except Exception:
                    pass
            return results

        completed_count = 0
        workers = min(self.max_workers, total)

        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_page = {
                executor.submit(_process_single_page, p_idx, file_bytes, dpi, shared_memory): p_idx
                for p_idx in page_indices
            }

            for future in concurrent.futures.as_completed(future_to_page):
                completed_count += 1
                try:
                    p_idx, text = future.result()
                    results[p_idx] = text
                except Exception as e:
                    failed_idx = future_to_page[future]
                    print(f"[PARALLEL EXTRACT EXCEPTION] Page {failed_idx}: {e}")
                    results[failed_idx] = ""

                if progress_callback:
                    try:
                        progress_callback(completed_count, total)
                    except Exception:
                        pass

        return results

    def extract_document_hybrid(
        self,
        file_bytes: bytes,
        dpi: int = 150,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Dict[int, str]:
        """
        Hybrid document extractor:
        - Extracts native vector text instantly (<0.05s per page).
        - Isolates scanned/image pages and runs parallel OCR across CPU cores.
        - Preserves strict sequential page order.

        Returns:
            Dict[int, str]: Ordered mapping of all pages (0..N-1) to extracted text.
        """
        if not file_bytes:
            return {}

        try:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
        except Exception as e:
            print(f"[HYBRID EXTRACT ERROR] Cannot open PDF stream: {e}")
            return {}

        try:
            total_pages = len(doc)
            page_texts: Dict[int, str] = {}
            scanned_indices: List[int] = []

            # 1. Fast vector text inspection
            for p_idx in range(total_pages):
                page = doc[p_idx]
                v_text = page.get_text()
                v_len = len(v_text.strip()) if v_text else 0
                has_images = len(page.get_images()) > 0

                # Pure vector text if substantial (>= 150 chars) or >= 10 chars with no raster images
                if v_len >= 150 or (v_len >= 10 and not has_images):
                    page_texts[p_idx] = v_text
                else:
                    scanned_indices.append(p_idx)
        finally:
            doc.close()

        # 2. Parallel OCR on scanned pages only
        if scanned_indices:
            ocr_results = self.extract_scanned_pages(
                file_bytes=file_bytes,
                page_indices=scanned_indices,
                dpi=dpi,
                progress_callback=progress_callback
            )
            page_texts.update(ocr_results)

        # 3. Ensure all pages are present in the dictionary
        for p_idx in range(total_pages):
            if p_idx not in page_texts:
                page_texts[p_idx] = ""

        return page_texts
