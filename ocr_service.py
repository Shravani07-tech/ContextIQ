# ocr_service.py
#
# Local OCR Service for ContextIQ 2.0.
# Handles optical character recognition for scanned/image PDFs using pytesseract & pdf2image.

import logging
import os
from typing import List, Tuple

logger = logging.getLogger(__name__)

try:
    import pytesseract
    from pdf2image import convert_from_path
    _OCR_AVAILABLE = True
except ImportError:
    _OCR_AVAILABLE = False


class OCRService:
    """Local OCR service for scanned PDF documents."""

    def __init__(self) -> None:
        self.available = _OCR_AVAILABLE

    def is_scanned_page(self, text: str) -> bool:
        """True if the page text is empty or contains insufficient text."""
        return not text or len(text.strip()) < 10

    def ocr_pdf(self, file_path: str) -> Tuple[List[Tuple[int, str]], str]:
        """
        Run local OCR on a PDF file page-by-page.

        Returns:
            (pages, extraction_method) where pages is [(page_num, text), ...]
            and extraction_method is "ocr" (or "text" if OCR was unavailable).
        """
        if not self.available:
            logger.warning(
                "OCR dependencies (pytesseract/pdf2image) missing. Skipping OCR for '%s'.",
                os.path.basename(file_path),
            )
            return [], "text"

        filename = os.path.basename(file_path)
        pages: List[Tuple[int, str]] = []

        try:
            images = convert_from_path(file_path)
            for page_num, image in enumerate(images, 1):
                try:
                    ocr_text = pytesseract.image_to_string(image)
                    if ocr_text and ocr_text.strip():
                        pages.append((page_num, ocr_text.strip()))
                except Exception as e:
                    logger.warning("OCR failed on page %d of '%s': %s", page_num, filename, e)

            return pages, "ocr" if pages else "text"

        except Exception as e:
            # Handles missing system Tesseract/Poppler binaries gracefully without crashing
            logger.error(
                "OCR failed for '%s'. Ensure tesseract and poppler system binaries are installed on PATH. Error: %s",
                filename,
                e,
            )
            return [], "text"


default_ocr_service = OCRService()
