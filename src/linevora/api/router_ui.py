"""UI serving: the React app (showcase + /panel) is served from a single port.

Priority: if `site/dist` (the Vite build output) exists it is served — `/` is the
showcase, `/panel` and below are the panel SPA, `/assets/*` are build assets.
Without a build, the plain panel bundled in the package (`linevora/web`) is
served for backward compatibility, so the panel opens even without a build.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, Response

router = APIRouter()

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
# src/linevora/api/router_ui.py -> project root: parents[3]
SITE_DIST = Path(__file__).resolve().parents[3] / "site" / "dist"


def _read(name: str) -> str:
    return (WEB_DIR / name).read_text(encoding="utf-8")


def _dist_index() -> Path | None:
    p = SITE_DIST / "index.html"
    return p if p.is_file() else None


def _serve_spa() -> FileResponse:
    idx = _dist_index()
    assert idx is not None
    return FileResponse(idx, media_type="text/html")


@router.get("/", response_class=HTMLResponse)
def index() -> Response:
    if _dist_index() is not None:
        return _serve_spa()
    return HTMLResponse(_read("index.html"))


@router.get("/panel", response_class=HTMLResponse)
@router.get("/panel/", response_class=HTMLResponse)
@router.get("/panel/{rest:path}", response_class=HTMLResponse)
def panel(rest: str = "") -> Response:
    _ = rest
    if _dist_index() is not None:
        return _serve_spa()
    return HTMLResponse(_read("index.html"))


@router.get("/assets/{file_path:path}")
def assets(file_path: str) -> Response:
    target = (SITE_DIST / "assets" / file_path).resolve()
    assets_root = (SITE_DIST / "assets").resolve()
    if assets_root not in target.parents and target != assets_root:
        raise HTTPException(status_code=404, detail="not found")
    if not target.is_file():
        raise HTTPException(status_code=404, detail="not found")
    return FileResponse(target)


@router.get("/app.js")
def app_js() -> Response:
    return Response(
        _read("app.js"),
        media_type="application/javascript",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get("/styles.css")
def styles_css() -> Response:
    return Response(
        _read("styles.css"),
        media_type="text/css",
        headers={"Cache-Control": "public, max-age=3600"},
    )
