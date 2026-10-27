from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.exception import Forbidden, PaymentNotFound
from app.dependencies.auth import CurrentUser, get_current_user
from app.dependencies.db import get_db
from app.schemas.api_response import ApiResponse
from app.schemas.payment_schema import CreatePaymentRequest, PaymentResponse
from app.services.order_service import OrderService
from app.services.payment_service import PaymentService

router = APIRouter(prefix="/order/{order_id}/payment", tags=["payment"])

payment_service = PaymentService()
order_service = OrderService()


def _ensure_owner_or_staff(order_id: int, current_user: CurrentUser, db: Session):
    order = order_service.get_order_by_id(db, order_id)
    if current_user.role not in ("admin", "staff") and order.user_id != current_user.id:
        raise Forbidden("You may only pay for your own orders")
    return order


@router.post("", response_model=ApiResponse[PaymentResponse])
def pay_for_order(
    order_id: int,
    request: CreatePaymentRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    _ensure_owner_or_staff(order_id, current_user, db)
    payment = payment_service.pay_for_order(db, order_id, request)
    return ApiResponse(success=True, message="Payment processed successfully", data=payment)


@router.get("", response_model=ApiResponse[PaymentResponse])
def get_payment(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    _ensure_owner_or_staff(order_id, current_user, db)
    payment = payment_service.get_payment_for_order(db, order_id)
    if payment is None:
        raise PaymentNotFound(order_id)
    return ApiResponse(success=True, message="Payment fetched successfully", data=payment)
