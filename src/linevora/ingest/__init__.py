"""Text extraction: preserves the page structure."""

from .extract import ExtractedDocument, Page, UnsupportedFormatError, extract_text

__all__ = ["ExtractedDocument", "Page", "UnsupportedFormatError", "extract_text"]
