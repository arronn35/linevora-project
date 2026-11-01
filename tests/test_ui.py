"""Arayüz sunumu ve talep listesi.

Yeni düzen: `/` ve `/panel` React SPA kabuğunu (site/dist) sunar;
dist yoksa yalın panele düşülür. `/app.js` + `/styles.css` geriye
dönük uyum için korunur.
"""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_index_serves_html(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    # React kabuğu ya da (dist yoksa) yalın panel — ikisi de geçerli giriş.
    assert ('id="root"' in response.text) or ("Linevora Panel" in response.text)


def test_panel_route_serves_spa(client):
    response = client.get("/panel")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert ('id="root"' in response.text) or ("Linevora Panel" in response.text)


def test_panel_deep_link_serves_spa(client):
    response = client.get("/panel/talepler")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_app_js_served(client):
    response = client.get("/app.js")
    assert response.status_code == 200
    assert "javascript" in response.headers["content-type"]
    assert "render()" in response.text


def test_styles_served(client):
    response = client.get("/styles.css")
    assert response.status_code == 200
    assert "text/css" in response.headers["content-type"]


def test_app_js_syntax():
    node = subprocess.run(["command", "-v", "node"], capture_output=True, text=True)
    if node.returncode != 0:
        import pytest

        pytest.skip("node yok, sözdizimi denetimi atlandı")
    from linevora.api.router_ui import WEB_DIR

    assert WEB_DIR.name == "web"
    checked = subprocess.run(
        ["node", "--check", str(WEB_DIR / "app.js")],
        capture_output=True,
        text=True,
    )
    assert checked.returncode == 0, checked.stderr


def test_inquiries_list(client, admin_token, inquiry_id):
    response = client.get(
        "/v1/inquiries", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    ids = [item["id"] for item in response.json()["inquiries"]]
    assert inquiry_id in ids


def test_inquiries_list_requires_auth(client):
    assert client.get("/v1/inquiries").status_code == 401


def test_ui_has_guidance(client):
    js = client.get("/app.js").text
    assert "0.85" in js  # skor açıklaması (yalın panel, geriye uyum)
    assert "copyGaps" in js  # soru listesini kopyalama
    assert "vSteps" in js  # akış göstergesi
    assert "roleHint" in js  # rol ipucu


def test_panel_source_has_guidance_and_observability():
    """React panel: rehber metinler + izleme (polling) kaynakta olmalı."""
    panel = ROOT / "site" / "src" / "panel"
    blob = "\n".join(p.read_text(encoding="utf-8") for p in panel.rglob("*.tsx"))
    blob += "\n".join(p.read_text(encoding="utf-8") for p in panel.rglob("*.ts"))
    assert "0.85" in blob  # skor açıklaması taşındı
    assert "Soru listesini kopyala" in blob
    assert "Canlı denetim akışı" in blob  # izlenebilir panel
    assert "usePolling" in blob or "useLive" in blob  # otomatik yenileme
