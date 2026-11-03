"""Catalog write surfaces: defining and listing products."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from typing import Any

from ..auth.roles import Role
from ..audit.store import AuditStore
from ..catalog.store import CatalogStore
from .deps import require_roles

router = APIRouter()


class ProductRequest(BaseModel):
    code: str
    names: list[str]
    synonyms: list[str] = []
    features: dict[str, Any] = {}
    unit: str = "pcs"


@router.post("/products", status_code=status.HTTP_201_CREATED)
def create_product(
    body: ProductRequest,
    request: Request,
    user: dict = Depends(require_roles(Role.ADMIN)),
) -> dict[str, object]:
    catalog: CatalogStore = request.app.state.catalog_store
    audit: AuditStore = request.app.state.audit_store
    if any(product.code == body.code for product in catalog.list()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="a product with this code already exists"
        )
    product = catalog.add(
        code=body.code,
        names=body.names,
        synonyms=body.synonyms,
        features=body.features,
        unit=body.unit,
    )
    audit.append(
        actor=user["subject"], action="product.create", target=f"product:{product.id}"
    )
    return {
        "id": product.id,
        "code": product.code,
        "names": list(product.names),
        "unit": product.unit,
    }


@router.get("/products")
def list_products(
    request: Request,
    user: dict = Depends(require_roles(Role.ADMIN, Role.SPECIALIST, Role.VIEWER)),
) -> dict[str, object]:
    _ = user
    catalog: CatalogStore = request.app.state.catalog_store
    return {
        "products": [
            {
                "id": product.id,
                "code": product.code,
                "names": list(product.names),
                "synonyms": list(product.synonyms),
                "features": product.features,
                "unit": product.unit,
            }
            for product in catalog.list()
        ]
    }
