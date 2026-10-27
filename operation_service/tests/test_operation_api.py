from decimal import Decimal

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


def test_unconfigured_payment_gateway_returns_503(client, db_session):
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
    order_id = order_res.json()["data"]["id"]

    # Direct customer checkout returns 503 until an external gateway provider is integrated
    pay_res = client.post(
        f"/order/{order_id}/payment",
        headers=customer_headers,
        json={"method": "card"},
    )
    assert pay_res.status_code == 503
    assert "not configured" in pay_res.json()["message"]


def test_order_creation_and_staff_advances_status_to_paid(client, db_session):
    cat = Category(name=f"{TEST_NAME_PREFIX}Pastries", description="Pastries")
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
        json={"items": [{"product_id": prod.id, "quantity": 2}]},
    )
    order_id = order_res.json()["data"]["id"]
    assert order_res.json()["data"]["status"] == "pending"

    # Verify inventory was decremented
    db_session.refresh(prod)
    assert prod.stock_quantity == 13

    # Staff verifies payment and advances status to paid
    staff_headers = auth_header(sub=2, role="staff")
    status_res = client.patch(
        f"/order/{order_id}/status",
        headers=staff_headers,
        json={"status": "paid"},
    )
    assert status_res.status_code == 200
    assert status_res.json()["data"]["status"] == "paid"

    # Order is now paid
    get_res = client.get(f"/order/{order_id}", headers=customer_headers)
    assert get_res.json()["data"]["status"] == "paid"
