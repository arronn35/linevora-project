"""Talep dosyalarından sayfa yapısını koruyarak metin çıkarma."""

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
    """Desteklenmeyen dosya biçimi ya da çözülemeyen içerik."""


MAX_PDF_PAGES = 200


def extract_text(filename: str, content: bytes) -> ExtractedDocument:
    lowered = filename.lower()
    if lowered.endswith(".pdf"):
        if not content.startswith(b"%PDF"):
            raise UnsupportedFormatError("PDF imzası (magic byte) doğrulanamadı")
        return _from_pdf(content)
    if lowered.endswith(TEXT_SUFFIXES):
        if content.startswith(b"%PDF"):
            raise UnsupportedFormatError("uzantı/içerik uyumsuz")
        return _from_text(content)
    raise UnsupportedFormatError(f"desteklenmeyen biçim: {filename}")


def _from_pdf(content: bytes) -> ExtractedDocument:
    from pypdf import PdfReader

    try:
        reader = PdfReader(BytesIO(content))
        if len(reader.pages) > MAX_PDF_PAGES:
            raise UnsupportedFormatError(f"PDF sayfa sınırı aşıldı ({MAX_PDF_PAGES})")
        pages = tuple(
            Page(number=index + 1, text=(page.extract_text() or ""))
            for index, page in enumerate(reader.pages)
        )
    except Exception as exc:
        raise UnsupportedFormatError(f"PDF okunamadı: {exc}")
    if not pages:
        raise UnsupportedFormatError("PDF içinde sayfa yok")
    return ExtractedDocument(pages=pages)


def _from_text(content: bytes) -> ExtractedDocument:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise UnsupportedFormatError("metin UTF-8 olarak çözülemedi")
    return ExtractedDocument(pages=(Page(number=1, text=text),))
