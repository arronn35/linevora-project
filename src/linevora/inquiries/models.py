"""Inquiry records (Inquiry / InquiryVersion in the data model)."""

from __future__ import annotations

from dataclasses import dataclass

from ..ingest.extract import Page


@dataclass(frozen=True)
class Inquiry:
    id: str
    customer: str
    title: str
    status: str = "open"
    created_by: str = ""
    tenant_id: str = "default"


@dataclass(frozen=True)
class InquiryVersion:
    id: str
    inquiry_id: str
    version_no: int
    file_id: str
    filename: str
    pages: tuple[Page, ...]
    created_at: float
