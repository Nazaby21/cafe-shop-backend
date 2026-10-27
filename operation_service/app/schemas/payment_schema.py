from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class CreatePaymentRequest(BaseModel):
    method: str = Field(pattern="^(cash|card|e_wallet)$")


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    order_id: int
    amount: Decimal
    method: str
    status: str
    transaction_ref: str
    failure_reason: str | None
