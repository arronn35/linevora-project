"""Talep açma, sürüm yükleme ve sürüm listeleme (Adım 3 kabulü)."""

import pytest
from reportlab.pdfgen import canvas

from linevora.files.store import LocalBlobStore


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _make_pdf(path, texts):
    painter = canvas.Canvas(str(path))
    for text in texts:
        painter.drawString(10, 700, text)
        painter.showPage()
    painter.save()
    return path.read_bytes()


def test_create_inquiry(client, admin_token):
    response = client.post(
        "/v1/inquiries",
        json={"customer": "Acme", "title": "Pompa"},
        headers=_auth(admin_token),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["customer"] == "Acme"
    assert body["status"] == "açık"


def test_create_inquiry_viewer_forbidden(client, viewer_token):
    response = client.post(
        "/v1/inquiries",
        json={"customer": "Acme", "title": "Pompa"},
        headers=_auth(viewer_token),
    )
    assert response.status_code == 403


def test_upload_text_version_preserves_content(client, admin_token, inquiry_id):
    response = client.post(
        f"/v1/inquiries/{inquiry_id}/versions",
        files={"file": ("sartname.txt", "DN50 pompa, 10 adet".encode("utf-8"))},
        headers=_auth(admin_token),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["version_no"] == 1
    assert body["pages"] == [{"number": 1, "text": "DN50 pompa, 10 adet"}]


def test_upload_pdf_version_preserves_pages(client, admin_token, inquiry_id, tmp_path):
    content = _make_pdf(
        tmp_path / "talep.pdf", ["Birinci sayfa gereksinim", "Ikinci sayfa miktar"]
    )
    response = client.post(
        f"/v1/inquiries/{inquiry_id}/versions",
        files={"file": ("talep.pdf", content, "application/pdf")},
        headers=_auth(admin_token),
    )
    assert response.status_code == 201
    pages = response.json()["pages"]
    assert [page["number"] for page in pages] == [1, 2]
    assert "Birinci sayfa" in pages[0]["text"]
    assert "Ikinci sayfa" in pages[1]["text"]


def test_versions_are_linked_and_numbered(client, admin_token, inquiry_id):
    for index in range(2):
        response = client.post(
            f"/v1/inquiries/{inquiry_id}/versions",
            files={"file": (f"v{index}.txt", f"içerik {index}".encode("utf-8"))},
            headers=_auth(admin_token),
        )
        assert response.status_code == 201
        assert response.json()["version_no"] == index + 1
    listing = client.get(
        f"/v1/inquiries/{inquiry_id}/versions", headers=_auth(admin_token)
    )
    assert listing.status_code == 200
    versions = listing.json()["versions"]
    assert [version["version_no"] for version in versions] == [1, 2]
    assert all(version["inquiry_id"] == inquiry_id for version in versions)


def test_viewer_can_list_but_not_upload(client, admin_token, viewer_token, inquiry_id):
    upload = client.post(
        f"/v1/inquiries/{inquiry_id}/versions",
        files={"file": ("x.txt", b"x")},
        headers=_auth(viewer_token),
    )
    assert upload.status_code == 403
    listing = client.get(
        f"/v1/inquiries/{inquiry_id}/versions", headers=_auth(viewer_token)
    )
    assert listing.status_code == 200


def test_upload_unsupported_format(client, admin_token, inquiry_id):
    response = client.post(
        f"/v1/inquiries/{inquiry_id}/versions",
        files={"file": ("tablo.xlsx", b"degil")},
        headers=_auth(admin_token),
    )
    assert response.status_code == 415


def test_upload_unknown_inquiry(client, admin_token):
    response = client.post(
        "/v1/inquiries/yok/versions",
        files={"file": ("x.txt", b"x")},
        headers=_auth(admin_token),
    )
    assert response.status_code == 404


def test_blob_store_is_content_addressed_and_immutable(tmp_path):
    store = LocalBlobStore(str(tmp_path))
    first = store.put("a.txt", "aynı".encode("utf-8"))
    second = store.put("b.txt", "aynı".encode("utf-8"))
    assert first.file_id == second.file_id
    assert store.get(first.file_id) == "aynı".encode("utf-8")
    with pytest.raises(KeyError):
        store.get("../kacis")
    with pytest.raises(KeyError):
        store.get("0" * 64)
