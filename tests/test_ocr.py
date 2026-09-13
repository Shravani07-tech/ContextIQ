# tests/test_ocr.py
from unittest.mock import MagicMock, patch
from ocr_service import OCRService
from parsers import PDFParser

def test_ocr_service_detection():
    service = OCRService()
    assert service.is_scanned_page("") is True
    assert service.is_scanned_page("   ") is True
    assert service.is_scanned_page("Short") is True
    assert service.is_scanned_page("This is a full page with sufficient text for extraction.") is False


@patch("ocr_service.pytesseract")
@patch("ocr_service.convert_from_path")
def test_ocr_service_ocr_pdf(mock_convert, mock_pytesseract, tmp_path):
    pdf_path = tmp_path / "scanned.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 dummy scanned content")

    mock_image = MagicMock()
    mock_convert.return_value = [mock_image]
    mock_pytesseract.image_to_string.return_value = "Scanned OCR Text Result"

    service = OCRService()
    service.available = True

    pages, method = service.ocr_pdf(str(pdf_path))
    assert method == "ocr"
    assert len(pages) == 1
    assert pages[0] == (1, "Scanned OCR Text Result")


def test_ocr_service_missing_binary(tmp_path):
    pdf_path = tmp_path / "scanned.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 dummy scanned content")

    service = OCRService()
    service.available = False

    pages, method = service.ocr_pdf(str(pdf_path))
    assert method == "text"
    assert pages == []
