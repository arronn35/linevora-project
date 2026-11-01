"""Yönlendiricilerin ortak yardımcıları."""

from __future__ import annotations

from fastapi import HTTPException, status

from ..inquiries.store import InquiryStore


def find_version(inquiries: InquiryStore, inquiry_id: str, version_no: int):
    try:
        versions = inquiries.list_versions(inquiry_id)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="talep yok")
    for version in versions:
        if version.version_no == version_no:
            return version
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="sürüm yok")
