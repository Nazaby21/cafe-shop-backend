from decimal import Decimal

from app.core.config import settings
from app.models.category import Category
from app.models.product import Product
from coffee_testing import TEST_NAME_PREFIX, auth_header


def test_list_products_public(client, db_session):
    cat = Category(name=f"{TEST_NAME_PREFIX}Coffee", description="Test Category")
    db_session.add(cat)
    db_session.flush()

    prod = Product(
        name=f"{TEST_NAME_PREFIX}Cold Brew",
        description="Fresh cold brew",
        price=Decimal("4.00"),
        stock_quantity=10,
        is_active=True,
        category_id=cat.id,
    )
    db_session.add(prod)
    db_session.commit()

    res = client.get("/product")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert len(data["data"]["items"]) >= 1


def test_create_order_and_pay(client, db_session):
    cat = Category(name=f"{TEST_NAME_PREFIX}Tea", description="Tea category")
    db_session.add(cat)
    db_session.flush()

    prod = Product(
        name=f"{TEST_NAME_PREFIX}Green Tea",
        description="Organic green tea",
        price=Decimal("3.00"),
        stock_quantity=20,
        is_active=True,
        category_id=cat.id,
    )
    db_session.add(prod)
    db_session.commit()
    db_session.refresh(prod)

    customer_headers = auth_header(sub=101, role="customer")
    order_res = client.post(
        "/order",
        headers=customer_headers,
        json={"items": [{"product_id": prod.id, "quantity": 2}]},
    )
    assert order_res.status_code == 200
    order_data = order_res.json()["data"]
    order_id = order_data["id"]
    assert order_data["status"] == "pending"

    # Verify stock decremented
    db_session.refresh(prod)
    assert prod.stock_quantity == 18

    # Pay for order
    pay_res = client.post(
        f"/order/{order_id}/payment",
        headers=customer_headers,
        json={"method": "card"},
    )
    assert pay_res.status_code == 200
    assert pay_res.json()["data"]["status"] == "success"

    # Order status advanced to paid
    get_order = client.get(f"/order/{order_id}", headers=customer_headers)
    assert get_order.json()["data"]["status"] == "paid"


def test_simulated_payment_blocked_in_production(client, db_session, monkeypatch):
    cat = Category(name=f"{TEST_NAME_PREFIX}Snacks", description="Snacks")
    db_session.add(cat)
    db_session.flush()

    prod = Product(
        name=f"{TEST_NAME_PREFIX}Croissant",
        description="Butter croissant",
        price=Decimal("2.50"),
        stock_quantity=15,
        is_active=True,
        category_id=cat.id,
    )
    db_session.add(prod)
    db_session.commit()

    customer_headers = auth_header(sub=102, role="customer")
    order_res = client.post(
        "/order",
        headers=customer_headers,
        json={"items": [{"product_id": prod.id, "quantity": 1}]},
    )
    order_id = order_res.json()["data"]["id"]

    # Switch environment to production
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "ALLOW_SIMULATED_PAYMENTS_IN_PROD", False)

    pay_res = client.post(
        f"/order/{order_id}/payment",
        headers=customer_headers,
        json={"method": "card"},
    )
    assert pay_res.status_code == 402  # PaymentRequired / PaymentFailed
    assert "disabled in production" in pay_res.json()["message"]
