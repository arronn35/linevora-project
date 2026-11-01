"""Talep deposu. MVP gerçeklemesi bellek içidir; kalıcı gerçekleme
Adım 8'de yönetilen veritabanıyla bu arayüzün arkasına geçer.
"""

from __future__ import annotations

import copy
import threading
import time
import uuid
from dataclasses import asdict
from typing import Protocol

from ..files.store import StoredFile
from ..ingest.extract import Page
from .models import Inquiry, InquiryVersion


class InquiryStore(Protocol):
    def create_inquiry(self, customer: str, title: str, created_by: str = "", tenant_id: str = "default") -> Inquiry:
        ...

    def get_inquiry(self, inquiry_id: str) -> Inquiry:
        ...

    def list(self) -> list[Inquiry]:
        ...

    def add_version(
        self, inquiry_id: str, stored: StoredFile, pages: tuple[Page, ...]
    ) -> InquiryVersion:
        ...

    def list_versions(self, inquiry_id: str) -> list[InquiryVersion]:
        ...

    def delete_inquiry(self, inquiry_id: str) -> None:
        ...


class InMemoryInquiryStore:
    def __init__(self) -> None:
        self._inquiries: dict[str, Inquiry] = {}
        self._versions: dict[str, list[InquiryVersion]] = {}
        self._lock = threading.Lock()

    def create_inquiry(self, customer: str, title: str, created_by: str = "", tenant_id: str = "default") -> Inquiry:
        with self._lock:
            inquiry = Inquiry(id=uuid.uuid4().hex, customer=customer, title=title, created_by=created_by, tenant_id=tenant_id)
            self._inquiries[inquiry.id] = inquiry
            self._versions[inquiry.id] = []
            return inquiry

    def get_inquiry(self, inquiry_id: str) -> Inquiry:
        with self._lock:
            try:
                return copy.deepcopy(self._inquiries[inquiry_id])
            except KeyError:
                raise KeyError(inquiry_id)

    def list(self) -> list[Inquiry]:
        with self._lock:
            return copy.deepcopy(list(self._inquiries.values()))

    def add_version(
        self, inquiry_id: str, stored: StoredFile, pages: tuple[Page, ...]
    ) -> InquiryVersion:
        with self._lock:
            if inquiry_id not in self._inquiries:
                raise KeyError(inquiry_id)
            versions = self._versions[inquiry_id]
            version = InquiryVersion(
                id=uuid.uuid4().hex,
                inquiry_id=inquiry_id,
                version_no=len(versions) + 1,
                file_id=stored.file_id,
                filename=stored.name,
                pages=pages,
                created_at=time.time(),
            )
            versions.append(version)
            return version

    def delete_inquiry(self, inquiry_id: str) -> None:
        with self._lock:
            if inquiry_id not in self._inquiries:
                raise KeyError(inquiry_id)
            del self._inquiries[inquiry_id]
            self._versions.pop(inquiry_id, None)

    def list_versions(self, inquiry_id: str) -> list[InquiryVersion]:
        with self._lock:
            try:
                return copy.deepcopy(list(self._versions[inquiry_id]))
            except KeyError:
                raise KeyError(inquiry_id)

    def to_snapshot(self) -> dict:
        with self._lock:
            return {
                "inquiries": [asdict(item) for item in self._inquiries.values()],
                "versions": {
                    key: [asdict(version) for version in versions]
                    for key, versions in self._versions.items()
                },
            }

    def load_snapshot(self, data: dict) -> None:
        with self._lock:
            self._inquiries = {
                item["id"]: Inquiry(**item) for item in data.get("inquiries", [])
            }
            rebuilt: dict[str, list[InquiryVersion]] = {}
            for key, versions in data.get("versions", {}).items():
                items = []
                for version in versions:
                    pages = tuple(Page(**page) for page in version["pages"])
                    items.append(
                        InquiryVersion(
                            id=version["id"],
                            inquiry_id=version["inquiry_id"],
                            version_no=version["version_no"],
                            file_id=version["file_id"],
                            filename=version["filename"],
                            pages=pages,
                            created_at=version["created_at"],
                        )
                    )
                rebuilt[key] = items
            self._versions = rebuilt
