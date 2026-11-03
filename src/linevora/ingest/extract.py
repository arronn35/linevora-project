"""Extracting text from inquiry files while preserving the page structure."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

TEXT_SUFFIXES = (".txt", ".md", ".text")


@dataclass(frozen=True)
class Page:
    number: int
    text: str


@dataclass(frozen=True)
class ExtractedDocument:
    pages: tuple[Page, ...]

    @property
    def full_text(self) -> str:
        return "\n\n".join(page.text for page in self.pages)


class UnsupportedFormatError(Exception):
    """Unsupported file format or undecodable content."""


MAX_PDF_PAGES = 200


def extract_text(filename: str, content: bytes) -> ExtractedDocument:
    lowered = filename.lower()
    if lowered.endswith(".pdf"):
        if not content.startswith(b"%PDF"):
            raise UnsupportedFormatError("could not verify the PDF signature (magic bytes)")
        return _from_pdf(content)
    if lowered.endswith(TEXT_SUFFIXES):
        if content.startswith(b"%PDF"):
            raise UnsupportedFormatError("extension/content mismatch")
        return _from_text(content)
    raise UnsupportedFormatError(f"unsupported format: {filename}")


def _from_pdf(content: bytes) -> ExtractedDocument:
    from pypdf import PdfReader

    try:
        reader = PdfReader(BytesIO(content))
        if len(reader.pages) > MAX_PDF_PAGES:
            raise UnsupportedFormatError(f"PDF page limit exceeded ({MAX_PDF_PAGES})")
        pages = tuple(
            Page(number=index + 1, text=(page.extract_text() or ""))
            for index, page in enumerate(reader.pages)
        )
    except Exception as exc:
        raise UnsupportedFormatError(f"could not read the PDF: {exc}")
    if not pages:
        raise UnsupportedFormatError("the PDF contains no pages")
    return ExtractedDocument(pages=pages)


def _from_text(content: bytes) -> ExtractedDocument:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise UnsupportedFormatError("the text could not be decoded as UTF-8")
    return ExtractedDocument(pages=(Page(number=1, text=text),))
