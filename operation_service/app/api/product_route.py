from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.dependencies.auth import CurrentUser, require_roles
from app.dependencies.db import get_db
from app.schemas.api_response import ApiResponse, PageMeta, PaginatedData
from app.schemas.product_schema import (
    AdjustStockRequest,
    CreateProductRequest,
    ProductResponse,
    UpdateProductRequest,
)
from app.services.product_service import ProductService

router = APIRouter(prefix="/product", tags=["product"])

product_service = ProductService()


@router.post("", response_model=ApiResponse[ProductResponse])
def add_product(
    request: CreateProductRequest,
    db: Session = Depends(get_db),
    _current_user: CurrentUser = Depends(require_roles("admin", "staff")),
):
    product = product_service.add_product(db, request)
    return ApiResponse(success=True, message="Product added successfully", data=product)


@router.get("", response_model=ApiResponse[PaginatedData[ProductResponse]])
def list_products(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    active_only: bool = Query(False, description="Only return currently available products"),
    db: Session = Depends(get_db),
):
    """Public menu listing - no authentication required to browse products."""
    items, meta = product_service.list_products(db, page=page, page_size=page_size, active_only=active_only)
    return ApiResponse(
        success=True,
        message="Products fetched successfully",
        data=PaginatedData(items=items, meta=PageMeta(**meta)),
    )


@router.get("/{product_id}", response_model=ApiResponse[ProductResponse])
def get_product(product_id: int, db: Session = Depends(get_db)):
    product = product_service.get_product_by_id(db, product_id)
    return ApiResponse(success=True, message="Product fetched successfully", data=product)


@router.put("/{product_id}", response_model=ApiResponse[ProductResponse])
def update_product(
    product_id: int,
    request: UpdateProductRequest,
    db: Session = Depends(get_db),
    _current_user: CurrentUser = Depends(require_roles("admin", "staff")),
):
    product = product_service.update_product(db, product_id, request)
    return ApiResponse(success=True, message="Product updated successfully", data=product)


@router.post("/{product_id}/stock", response_model=ApiResponse[ProductResponse])
def adjust_stock(
    product_id: int,
    request: AdjustStockRequest,
    db: Session = Depends(get_db),
    _current_user: CurrentUser = Depends(require_roles("admin", "staff")),
):
    product = product_service.adjust_stock(db, product_id, request)
    return ApiResponse(success=True, message="Stock adjusted successfully", data=product)


@router.delete("/{product_id}", response_model=ApiResponse[ProductResponse])
def deactivate_product(
    product_id: int,
    db: Session = Depends(get_db),
    _current_user: CurrentUser = Depends(require_roles("admin", "staff")),
):
    product = product_service.deactivate(db, product_id)
    return ApiResponse(success=True, message="Product deactivated successfully", data=product)
