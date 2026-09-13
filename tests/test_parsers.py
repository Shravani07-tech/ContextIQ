# tests/test_parsers.py
import os
import pytest
from parsers import (
    NormalizedDocument,
    ParserRegistry,
    TextParser,
    PDFParser,
    default_registry,
)

def test_text_parser(tmp_path):
    txt_file = tmp_path / "sample.txt"
    txt_file.write_text("Hello ContextIQ 2.0!", encoding="utf-8")

    parser = TextParser()
    assert parser.can_parse("sample.txt") is True
    assert parser.can_parse("sample.pdf") is False

    doc = parser.parse(str(txt_file))
    assert isinstance(doc, NormalizedDocument)
    assert doc.filename == "sample.txt"
    assert doc.text == "Hello ContextIQ 2.0!"
    assert doc.file_type == "txt"
    assert doc.pages is None


def test_parser_registry(tmp_path):
    registry = ParserRegistry()
    txt_file = tmp_path / "doc.txt"
    txt_file.write_text("Registry Test", encoding="utf-8")

    parser = registry.get_parser("doc.txt")
    assert parser is not None
    assert isinstance(parser, TextParser)

    doc = registry.parse_file(str(txt_file))
    assert doc.text == "Registry Test"

    with pytest.raises(ValueError, match="Unsupported file type"):
        registry.parse_file("unknown.xyz")
