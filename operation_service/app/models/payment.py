from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class PaymentStatus:
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"

    ALL = (PENDING, SUCCESS, FAILED)


class PaymentMethod:
    CASH = "cash"
    CARD = "card"
    E_WALLET = "e_wallet"

    ALL = (CASH, CARD, E_WALLET)


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )

    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    method: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=PaymentStatus.PENDING)
    # Gateway reference or transaction identifier.
    transaction_ref: Mapped[str] = mapped_column(String(64), nullable=False)
    failure_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    order: Mapped["Order"] = relationship(back_populates="payment")
