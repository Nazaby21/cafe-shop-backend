from http import HTTPStatus


class ApplicationError(Exception):
    def __init__(self, message: str, error_code: str, status_code: int):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        super().__init__(message)


# ---------------------------------------------------------------- auth (401/403)
class Unauthorized(ApplicationError):
    def __init__(self, message: str = "Authentication is required to access this resource"):
        super().__init__(message=message, error_code="err_401", status_code=HTTPStatus.UNAUTHORIZED)


class Forbidden(ApplicationError):
    def __init__(self, message: str = "You do not have permission to perform this action"):
        super().__init__(message=message, error_code="err_403", status_code=HTTPStatus.FORBIDDEN)


class InvalidToken(ApplicationError):
    def __init__(self):
        super().__init__(
            message="Invalid authentication token",
            error_code="err_401_invalid_token",
            status_code=HTTPStatus.UNAUTHORIZED,
        )


class TokenExpired(ApplicationError):
    def __init__(self):
        super().__init__(
            message="Authentication token has expired",
            error_code="err_401_token_expired",
            status_code=HTTPStatus.UNAUTHORIZED,
        )


# --------------------------------------------------------------------- product
class ProductNotFound(ApplicationError):
    def __init__(self, product_id: int):
        super().__init__(
            message=f"Product with id {product_id} not found",
            error_code="err_404_product",
            status_code=HTTPStatus.NOT_FOUND,
        )


class ProductNameAlreadyExists(ApplicationError):
    def __init__(self, name: str):
        super().__init__(
            message=f"Product with name '{name}' already exists",
            error_code="err_409_product_name",
            status_code=HTTPStatus.CONFLICT,
        )


class ProductInactive(ApplicationError):
    def __init__(self, product_id: int):
        super().__init__(
            message=f"Product with id {product_id} is not currently available",
            error_code="err_409_product_inactive",
            status_code=HTTPStatus.CONFLICT,
        )


# ----------------------------------------------------------------------- stock
class InsufficientStock(ApplicationError):
    def __init__(self, product_id: int, requested: int, available: int):
        super().__init__(
            message=(
                f"Insufficient stock for product {product_id}: "
                f"requested {requested}, only {available} available"
            ),
            error_code="err_409_insufficient_stock",
            status_code=HTTPStatus.CONFLICT,
        )


class InvalidStockAdjustment(ApplicationError):
    def __init__(self, message: str = "Stock adjustment quantity must be non-zero"):
        super().__init__(message=message, error_code="err_400_stock_adjustment", status_code=HTTPStatus.BAD_REQUEST)


# ----------------------------------------------------------------------- order
class OrderNotFound(ApplicationError):
    def __init__(self, order_id: int):
        super().__init__(
            message=f"Order with id {order_id} not found",
            error_code="err_404_order",
            status_code=HTTPStatus.NOT_FOUND,
        )


class EmptyOrder(ApplicationError):
    def __init__(self):
        super().__init__(
            message="An order must contain at least one item",
            error_code="err_400_empty_order",
            status_code=HTTPStatus.BAD_REQUEST,
        )


class InvalidOrderStatusTransition(ApplicationError):
    def __init__(self, current_status: str, target_status: str):
        super().__init__(
            message=f"Cannot move order from '{current_status}' to '{target_status}'",
            error_code="err_409_order_status",
            status_code=HTTPStatus.CONFLICT,
        )


# --------------------------------------------------------------------- payment
class PaymentAlreadyExists(ApplicationError):
    def __init__(self, order_id: int):
        super().__init__(
            message=f"A successful payment already exists for order {order_id}",
            error_code="err_409_payment_exists",
            status_code=HTTPStatus.CONFLICT,
        )


class PaymentNotFound(ApplicationError):
    def __init__(self, order_id: int):
        super().__init__(
            message=f"No payment has been recorded for order {order_id} yet",
            error_code="err_404_payment",
            status_code=HTTPStatus.NOT_FOUND,
        )


class OrderNotPayable(ApplicationError):
    def __init__(self, order_id: int, status: str):
        super().__init__(
            message=f"Order {order_id} cannot be paid because its status is '{status}'",
            error_code="err_409_order_not_payable",
            status_code=HTTPStatus.CONFLICT,
        )


class PaymentFailed(ApplicationError):
    def __init__(self, reason: str = "Payment processing failed"):
        super().__init__(message=reason, error_code="err_402_payment_failed", status_code=HTTPStatus.PAYMENT_REQUIRED)
