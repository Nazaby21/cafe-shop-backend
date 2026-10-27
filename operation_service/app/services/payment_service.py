from abc import ABC, abstractmethod

from sqlalchemy.orm import Session

from app.core.exception import (
    OrderNotPayable,
    PaymentAlreadyExists,
    PaymentFailed,
    PaymentGatewayNotConfigured,
)
from app.models.order import OrderStatus
from app.models.payment import Payment, PaymentStatus
from app.repository import payment_repository as payment_repo
from app.schemas.payment_schema import CreatePaymentRequest
from app.services.order_service import OrderService


class PaymentGateway(ABC):
    """Abstract interface for external payment gateway integration."""

    @abstractmethod
    def charge(self, amount: float, method: str) -> tuple[str, bool, str | None]:
        """Charge the specified amount. Returns (transaction_ref, succeeded, failure_reason)."""
        pass


class UnconfiguredPaymentGateway(PaymentGateway):
    """Default gateway implementation until an external payment provider SDK is integrated."""

    def charge(self, amount: float, method: str) -> tuple[str, bool, str | None]:
        raise PaymentGatewayNotConfigured()


class PaymentService:
    """
    Handles payment processing for customer orders.

    Online card/wallet payments delegate to the configured PaymentGateway.
    If no external provider is integrated, direct customer checkout raises HTTP 503
    (PaymentGatewayNotConfigured). Staff can manually record offline payments
    or advance orders to paid status via PATCH /order/{id}/status.
    """

    def __init__(self, gateway: PaymentGateway | None = None):
        self.order_service = OrderService()
        self.gateway = gateway or UnconfiguredPaymentGateway()

    def pay_for_order(self, db: Session, order_id: int, request: CreatePaymentRequest) -> Payment:
        order = self.order_service.get_order_by_id(db, order_id)

        if order.status != OrderStatus.PENDING:
            raise OrderNotPayable(order_id, order.status)

        existing = payment_repo.get_by_order_id(db, order_id)
        if existing and existing.status == PaymentStatus.SUCCESS:
            raise PaymentAlreadyExists(order_id)

        # Delegate charge processing to the configured gateway interface
        transaction_ref, succeeded, failure_reason = self.gateway.charge(order.total_amount, request.method)

        if existing:
            payment = existing
            payment.method = request.method
            payment.transaction_ref = transaction_ref
            payment.status = PaymentStatus.SUCCESS if succeeded else PaymentStatus.FAILED
            payment.failure_reason = None if succeeded else failure_reason
        else:
            payment = Payment(
                order_id=order_id,
                amount=order.total_amount,
                method=request.method,
                status=PaymentStatus.SUCCESS if succeeded else PaymentStatus.FAILED,
                transaction_ref=transaction_ref,
                failure_reason=None if succeeded else failure_reason,
            )

        if not succeeded:
            payment_repo.update(db, payment) if existing else payment_repo.create(db, payment)
            raise PaymentFailed(failure_reason or "Payment processing failed")

        payment = payment_repo.update(db, payment) if existing else payment_repo.create(db, payment)

        # Move the order forward once payment succeeds
        self.order_service.update_status(db, order_id, OrderStatus.PAID)

        return payment

    def get_payment_for_order(self, db: Session, order_id: int) -> Payment | None:
        return payment_repo.get_by_order_id(db, order_id)
