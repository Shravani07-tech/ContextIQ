# parsers.py
#
# Unified document parser architecture for ContextIQ 2.0.
# Translates various file formats into a single NormalizedDocument representation.

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from pypdf import PdfReader

logger = logging.getLogger(__name__)

# References / Bibliography heading detector for back-matter stripping.
_REFERENCES_HEADING = re.compile(
    r"(?im)^[ \t]*(?:\d+\.|[IVXLCDM]+\.)?[ \t]*(references|bibliography|works cited)(?:[ \t]+and[ \t]+(?:references|bibliography|works cited))?[ \t]*$"
)


def strip_references(text: str) -> str:
    """
    Remove a trailing References/Bibliography section if present in the latter half of the document.
    """
    for match in _REFERENCES_HEADING.finditer(text):
        if match.start() > len(text) * 0.5:
            return text[: match.start()]
    return text


@dataclass
class NormalizedDocument:
    """
    Normalized internal document model representing extracted content from any supported file type.
    """

    filename: str
    text: str
    file_type: str
    document_id: str
    source_path: Optional[str] = None
    pages: Optional[List[Tuple[int, str]]] = None  # [(page_num, text), ...]
    slides: Optional[List[Tuple[int, str]]] = None  # [(slide_num, text), ...]
    sheets: Optional[List[Tuple[str, str]]] = None  # [(sheet_name, text), ...]
    sections: Optional[List[Tuple[str, str]]] = None  # [(heading, text), ...]
    metadata: Dict[str, Any] = field(default_factory=dict)
    extraction_method: str = "text"  # "text" | "ocr"


class BaseParser(ABC):
    """Abstract base class for all file format parsers."""

    @abstractmethod
    def can_parse(self, filename: str) -> bool:
        """Return True if this parser supports the given filename/extension."""
        pass

    @abstractmethod
    def parse(self, file_path: str) -> NormalizedDocument:
        """Parse file at `file_path` and return a NormalizedDocument."""
        pass


class TextParser(BaseParser):
    """Parser for plain text files (.txt)."""

    def can_parse(self, filename: str) -> bool:
        return filename.lower().endswith(".txt")

    def parse(self, file_path: str) -> NormalizedDocument:
        filename = os.path.basename(file_path)
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()

        return NormalizedDocument(
            filename=filename,
            text=text,
            file_type="txt",
            document_id=filename,
            source_path=file_path,
            pages=None,
            extraction_method="text",
        )


class PDFParser(BaseParser):
    """Parser for PDF documents (.pdf)."""

    def can_parse(self, filename: str) -> bool:
        return filename.lower().endswith(".pdf")

    def parse(self, file_path: str) -> NormalizedDocument:
        filename = os.path.basename(file_path)
        reader = PdfReader(file_path)
        pages: List[Tuple[int, str]] = []

        for page_num, page in enumerate(reader.pages, 1):
            text = page.extract_text()
            if text and text.strip():
                pages.append((page_num, text))

        full_text = "\n".join(text for _, text in pages)
        extraction_method = "text"

        return NormalizedDocument(
            filename=filename,
            text=full_text,
            file_type="pdf",
            document_id=filename,
            source_path=file_path,
            pages=pages,
            extraction_method=extraction_method,
        )


class ParserRegistry:
    """Registry managing available document parsers."""

    def __init__(self) -> None:
        self._parsers: List[BaseParser] = [
            TextParser(),
            PDFParser(),
        ]

    def register_parser(self, parser: BaseParser) -> None:
        """Register a new parser instance."""
        self._parsers.append(parser)

    def get_parser(self, filename: str) -> Optional[BaseParser]:
        """Find the matching parser for a given filename."""
        for parser in self._parsers:
            if parser.can_parse(filename):
                return parser
        return None

    def parse_file(self, file_path: str) -> NormalizedDocument:
        """Parse a file using the registered parsers."""
        filename = os.path.basename(file_path)
        parser = self.get_parser(filename)
        if not parser:
            raise ValueError(f"Unsupported file type: {filename}")
        return parser.parse(file_path)


# Global registry singleton instance
default_registry = ParserRegistry()
