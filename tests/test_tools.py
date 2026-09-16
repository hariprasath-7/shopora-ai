import json

import pytest

from src.database import Base, SessionLocal, engine
from src.models import Customer, Product
from src.tools import (
    add_to_cart,
    checkout,
    compare_products,
    compute_match_score,
    extract_specs,
    get_order_history,
    get_product_image,
    make_payment,
    recommend_products,
    remove_from_cart,
    update_cart_quantity,
    update_order_status,
    view_cart,
)


@pytest.fixture(autouse=True)
def setup_database():
    """Ensure tables exist and seed sample product for tool testing."""
    Base.metadata.create_all(engine)
    session = SessionLocal()

    if not session.query(Customer).filter(Customer.id == 9876).first():
        session.add(Customer(id=9876, name="Tool Test", email="tool-test@example.com", hashed_password="test"))
        session.commit()

    p = session.query(Product).filter(Product.id == 9999).first()
    if not p:
        test_prod = Product(
            id=9999,
            name="Fixture Smart Watch",
            description="High-tech smartwatch with fitness tracking and heart rate monitor",
            category="Accessories",
            price=4999.0,
            rating=4.6,
            stock=15,
        )
        session.add(test_prod)
        session.commit()
    session.close()


def test_extract_specs():
    desc = "High-performance laptop with 16GB RAM, 512GB SSD, and RTX 4060 graphics."
    specs = extract_specs(desc)
    assert len(specs) > 0
    assert any("RAM" in s or "laptop" in s.lower() or "512GB" in s for s in specs)


def test_get_product_image():
    img_laptop = get_product_image("laptop")
    assert "unsplash.com" in img_laptop
    img_default = get_product_image("unknown_category")
    assert "unsplash.com" in img_default


def test_compute_match_score():
    class DummyProduct:
        price = 50000.0
        category = "Laptop"
        description = "Powerful laptop for AI development and gaming"
        name = "AI Beast Laptop"
        rating = 4.8

    p = DummyProduct()
    score, reason = compute_match_score(
        p,
        max_price=60000.0,
        category="laptop",
        search_term="AI development",
    )

    assert score >= 70
    assert "under budget" in reason or "rating" in reason.lower() or "match" in reason.lower()


def test_cart_workflow():
    config = {"configurable": {"thread_id": "test-cart-session", "user_id": 9876}}

    # Add to cart
    res_add = add_to_cart.invoke({"product_id": 9999, "quantity": 2}, config=config)
    assert "Added 2 x Fixture Smart Watch" in res_add

    # View cart
    res_view = view_cart.invoke({}, config=config)
    cart_data = json.loads(res_view)
    assert len(cart_data["items"]) >= 1
    assert cart_data["total"] >= 9998.0

    # Update quantity
    res_update = update_cart_quantity.invoke({"product_id": 9999, "quantity": 1}, config=config)
    assert "Cart updated" in res_update

    # Remove from cart
    res_remove = remove_from_cart.invoke({"product_id": 9999}, config=config)
    assert "Removed from your cart" in res_remove


def test_checkout_and_order_lifecycle():
    config = {"configurable": {"thread_id": "test-order-session", "user_id": 9876}}

    # Add item
    add_to_cart.invoke({"product_id": 9999, "quantity": 1}, config=config)

    # Checkout
    res_checkout = checkout.invoke({}, config=config)
    order_data = json.loads(res_checkout)
    order_id = order_data["order_id"]
    assert order_data["status"] == "pending"

    # History
    res_history = get_order_history.invoke({}, config=config)
    history_data = json.loads(res_history)
    assert any(o["order_id"] == order_id for o in history_data)

    # Payment
    res_pay = make_payment.invoke({"order_id": order_id, "method": "upi"}, config=config)
    pay_data = json.loads(res_pay)
    assert pay_data["status"] == "confirmed"

    # Status update (admin-only operation)
    admin_config = {"configurable": {"thread_id": "test-order-session", "user_id": 9876, "user_role": "admin"}}
    res_status = update_order_status.invoke({"order_id": order_id, "status": "processing"}, config=admin_config)
    assert "Order status updated" in res_status


def test_update_order_status_requires_admin():
    config = {"configurable": {"thread_id": "test-order-session-2", "user_id": 9876}}
    add_to_cart.invoke({"product_id": 9999, "quantity": 1}, config=config)
    order_data = json.loads(checkout.invoke({}, config=config))

    res_status = update_order_status.invoke(
        {"order_id": order_data["order_id"], "status": "processing"}, config=config
    )
    assert "administrators" in res_status


def test_recommend_and_compare():
    res_rec = recommend_products.invoke({"category": "Accessories", "max_price": 10000.0})
    rec_data = json.loads(res_rec)
    assert "recommendations" in rec_data
    assert len(rec_data["recommendations"]) >= 1

    res_comp = compare_products.invoke({"product_ids": [9999, 9999]})
    comp_data = json.loads(res_comp)
    assert "products" in comp_data
