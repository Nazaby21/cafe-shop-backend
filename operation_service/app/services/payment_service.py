import secrets

from sqlalchemy.orm import Session

from app.core.exception import OrderNotPayable, PaymentAlreadyExists, PaymentFailed
from app.models.order import OrderStatus
from app.models.payment import Payment, PaymentStatus
from app.repository import order_repository as order_repo
from app.repository import payment_repository as payment_repo
from app.schemas.payment_schema import CreatePaymentRequest
from app.services.order_service import OrderService


class PaymentService:
    """
    Simulates a payment gateway. There is no real external payment provider
    wired up here - this generates a fake transaction reference and marks
    the payment as successful, which is enough to drive the order lifecycle
    (pending -> paid) in this coursework-scale system. Swap `_charge()` for
    a real gateway SDK call to go to production.
    """

    def __init__(self):
        self.order_service = OrderService()

    def pay_for_order(self, db: Session, order_id: int, request: CreatePaymentRequest) -> Payment:
        order = self.order_service.get_order_by_id(db, order_id)

        if order.status != OrderStatus.PENDING:
            raise OrderNotPayable(order_id, order.status)

        existing = payment_repo.get_by_order_id(db, order_id)
        if existing and existing.status == PaymentStatus.SUCCESS:
            raise PaymentAlreadyExists(order_id)

        transaction_ref, succeeded, failure_reason = self._charge(order.total_amount, request.method)

        if existing:
            # Retry a previously-failed payment attempt instead of creating a duplicate row.
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

        # Move the order forward now that payment succeeded.
        self.order_service.update_status(db, order_id, OrderStatus.PAID)

        return payment

    def get_payment_for_order(self, db: Session, order_id: int) -> Payment | None:
        return payment_repo.get_by_order_id(db, order_id)

    @staticmethod
    def _charge(amount, method: str) -> tuple[str, bool, str | None]:
        """Deterministic simulation: always succeeds for a positive amount."""
        transaction_ref = f"SIM-{method.upper()}-{secrets.token_hex(6)}"
        if amount is None or float(amount) <= 0:
            return transaction_ref, False, "Order total must be greater than zero"
        return transaction_ref, True, None
