"""LangChain tools for Shopora. User-owned state is always scoped by customer_id."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from langchain.tools import tool
from langchain_core.runnables import RunnableConfig
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from .database import SessionLocal
from .models import Cart, Customer, Order, OrderItem, Payment, Product, Shipment
from .rag import build_grounded_context
from .recommendations import recommend_for_user
from .repository import (
    filter_products as db_filter_products,
)
from .repository import (
    get_product as db_get_product,
)
from .repository import (
    get_reviews as db_get_reviews,
)
from .search_service import hybrid_search

CATEGORY_IMAGES = {
    "laptop": "https://images.unsplash.com/photo-1603302576837-37561b2e2302?auto=format&fit=crop&w=900&q=85",
    "monitor": "https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?auto=format&fit=crop&w=900&q=85",
    "mouse": "https://images.unsplash.com/photo-1527864550417-7fd91fc51a46?auto=format&fit=crop&w=900&q=85",
    "keyboard": "https://images.unsplash.com/photo-1587829741301-dc798b83add3?auto=format&fit=crop&w=900&q=85",
    "headphones": "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?auto=format&fit=crop&w=900&q=85",
    "accessories": "https://images.unsplash.com/photo-1625723044792-44de16ccb4e8?auto=format&fit=crop&w=900&q=85",
    "gaming": "https://images.unsplash.com/photo-1606144042614-b2417e99c4e3?auto=format&fit=crop&w=900&q=85",
    "camera": "https://images.unsplash.com/photo-1587826080692-f439cd0b70da?auto=format&fit=crop&w=900&q=85",
    "storage": "https://images.unsplash.com/photo-1531492746076-161ca9bcad58?auto=format&fit=crop&w=900&q=85",
    "speaker": "https://images.unsplash.com/photo-1608043152269-423dbba4e7e1?auto=format&fit=crop&w=900&q=85",
}

DEFAULT_IMAGE = (
    "https://images.unsplash.com/photo-1518770660439-4636190af475"
    "?auto=format&fit=crop&w=900&q=85"
)


def get_product_image(category: str) -> str:
    return CATEGORY_IMAGES.get((category or "").lower(), DEFAULT_IMAGE)


def extract_specs(description: str) -> list[str]:
    import re

    if not description:
        return []

    phrases = re.split(r"[,.]", description)
    specs = []

    for phrase in phrases:
        phrase = re.sub(
            r"^(and|with|for|or)\s+",
            "",
            phrase.strip(),
            flags=re.IGNORECASE,
        )

        if 5 <= len(phrase) <= 55 and not any(
            x in phrase.lower()
            for x in [
                "designed for",
                "suitable for",
                "ideal for",
                "perfect for",
            ]
        ):
            specs.append(phrase)

    return list(dict.fromkeys(specs))[:6] or [description[:50]]


def product_to_dict(product, include_image: bool = True) -> dict:
    data = {
        "id": product.id,
        "name": product.name,
        "description": product.description,
        "category": product.category,
        "price": float(product.price),
        "rating": float(product.rating),
        "stock": product.stock,
    }

    if include_image:
        data["image"] = get_product_image(product.category)
        data["specs"] = extract_specs(product.description)

    return data


def compute_match_score(
    product,
    max_price=None,
    category=None,
    search_term=None,
):
    budget = (
        100
        if max_price is None
        else (
            100
            if product.price <= max_price
            else max(
                0,
                100 - ((product.price - max_price) / max_price) * 300,
            )
        )
    )

    cat = (
        50
        if not category
        else (
            100
            if product.category.lower() == category.lower()
            else (
                60
                if category.lower() in product.description.lower()
                else 20
            )
        )
    )

    use = 50

    if search_term:
        words = search_term.lower().split()
        text = f"{product.name} {product.description}".lower()

        use = (
            100 * sum(w in text for w in words)
            / max(len(words), 1)
        )

    score = round(
        budget * 0.30
        + cat * 0.25
        + (product.rating / 5) * 100 * 0.20
        + use * 0.15
        + min(100, product.rating * 20) * 0.10
    )

    return (
        min(99, max(1, score)),
        (
            "Strong match"
            if score >= 80
            else "Good match"
            if score >= 60
            else "Partial match"
        ),
    )


def _config(config):
    if isinstance(config, dict):
        return config.get("configurable", {}) or {}

    return (
        config.get("configurable", {})
        if config and hasattr(config, "get")
        else {}
    )


def get_thread_id(config):
    return _config(config).get("thread_id")


def get_user_id(config):
    value = _config(config).get("user_id")

    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def get_user_role(config):
    return _config(config).get("user_role", "customer")


def _require_user(config):
    user_id = get_user_id(config)

    if not user_id:
        raise RuntimeError("Authenticated user context is required")

    return user_id


@tool
def get_product(product_id: int) -> str:
    """Get detailed information about a product by its product ID."""
    with SessionLocal() as db:
        product = db_get_product(db, product_id)

        return (
            json.dumps(product_to_dict(product))
            if product
            else f"No product found with ID {product_id}."
        )


@tool
def search_products(search_term: str) -> str:
    """Search the product catalog using hybrid keyword and semantic search."""
    with SessionLocal() as db:
        rows = hybrid_search(db, search_term, 12)

        result = []

        for product, score, source in rows:
            data = product_to_dict(product)

            match, reason = compute_match_score(
                product,
                search_term=search_term,
            )

            data.update(
                match_score=match,
                reason=f"{reason}; {source} retrieval",
            )

            result.append(data)

        return json.dumps(result)


@tool
def get_reviews(product_id: int) -> str:
    """Get customer reviews and ratings for a specific product."""
    with SessionLocal() as db:
        reviews = db_get_reviews(db, product_id)

        return (
            json.dumps(
                [
                    {
                        "id": r.id,
                        "product_id": r.product_id,
                        "review_text": r.review_text,
                        "rating": r.rating,
                    }
                    for r in reviews
                ]
            )
            if reviews
            else f"No reviews found for product ID {product_id}."
        )


@tool
def filter_products(
    search_term=None,
    category=None,
    min_price=None,
    max_price=None,
    min_rating=None,
) -> str:
    """Filter products by search term, category, price range, and rating."""
    with SessionLocal() as db:
        products = db_filter_products(
            db,
            search_term,
            category,
            min_price,
            max_price,
            min_rating,
        )

        return json.dumps(
            [product_to_dict(p) for p in products[:20]]
        )


@tool
def answer_product_question(question: str) -> str:
    """Answer a product question using grounded information from the product catalog."""
    with SessionLocal() as db:
        return build_grounded_context(db, question, 5)


@tool
def add_to_cart(
    product_id: int,
    quantity: int = 1,
    config: RunnableConfig = None,
) -> str:
    """Add a specified quantity of a product to the authenticated user's cart."""
    user_id = _require_user(config)

    if quantity <= 0:
        return "Quantity must be greater than 0."

    with SessionLocal() as db:
        product = db.get(Product, product_id)

        if not product:
            return "Product not found."

        item = db.scalar(
            select(Cart).where(
                Cart.customer_id == user_id,
                Cart.product_id == product_id,
            )
        )

        new_qty = (item.quantity if item else 0) + quantity

        if new_qty > product.stock:
            return f"Only {product.stock} units are available."

        if item:
            item.quantity = new_qty
        else:
            db.add(
                Cart(
                    customer_id=user_id,
                    thread_id=get_thread_id(config),
                    product_id=product_id,
                    quantity=quantity,
                )
            )

        db.commit()

        return f"Added {quantity} x {product.name} to your cart."


@tool
def view_cart(config: RunnableConfig = None) -> str:
    """View all products currently in the authenticated user's cart."""
    user_id = _require_user(config)

    with SessionLocal() as db:
        items = db.scalars(
            select(Cart)
            .options(selectinload(Cart.product))
            .where(Cart.customer_id == user_id)
        ).all()

        result = []
        total = 0.0

        for item in items:
            subtotal = float(item.product.price) * item.quantity
            total += subtotal

            result.append(
                {
                    "product_id": item.product.id,
                    "name": item.product.name,
                    "price": float(item.product.price),
                    "quantity": item.quantity,
                    "subtotal": subtotal,
                }
            )

        return (
            json.dumps({"items": result, "total": total})
            if result
            else "Your cart is currently empty."
        )


@tool
def remove_from_cart(
    product_id: int,
    config: RunnableConfig = None,
) -> str:
    """Remove a product from the authenticated user's cart."""
    user_id = _require_user(config)

    with SessionLocal() as db:
        item = db.scalar(
            select(Cart).where(
                Cart.customer_id == user_id,
                Cart.product_id == product_id,
            )
        )

        if not item:
            return "That product is not in your cart."

        db.delete(item)
        db.commit()

        return "Removed from your cart."


@tool
def update_cart_quantity(
    product_id: int,
    quantity: int,
    config: RunnableConfig = None,
) -> str:
    """Update the quantity of a product in the authenticated user's cart."""
    user_id = _require_user(config)

    with SessionLocal() as db:
        item = db.scalar(
            select(Cart)
            .options(selectinload(Cart.product))
            .where(
                Cart.customer_id == user_id,
                Cart.product_id == product_id,
            )
        )

        if not item:
            return "That product is not in your cart."

        if quantity < 0 or quantity > item.product.stock:
            return (
                f"Quantity must be between 0 and "
                f"{item.product.stock}."
            )

        if quantity == 0:
            db.delete(item)
        else:
            item.quantity = quantity

        db.commit()

        return "Cart updated."


@tool
def checkout(config: RunnableConfig = None) -> str:
    """Create an order from the authenticated user's cart and reduce product stock."""
    user_id = _require_user(config)

    with SessionLocal() as db:
        items = db.scalars(
            select(Cart)
            .options(selectinload(Cart.product))
            .where(Cart.customer_id == user_id)
            .with_for_update()
        ).all()

        if not items:
            return "Your cart is empty."

        total = 0.0

        for item in items:
            if item.quantity > item.product.stock:
                return (
                    f"Insufficient stock for "
                    f"{item.product.name}."
                )

            total += float(item.product.price) * item.quantity

        order = Order(
            customer_id=user_id,
            thread_id=get_thread_id(config),
            total_amount=total,
            status="pending",
        )

        db.add(order)
        db.flush()

        for item in items:
            db.add(
                OrderItem(
                    order_id=order.id,
                    product_id=item.product_id,
                    quantity=item.quantity,
                    price=item.product.price,
                )
            )

            item.product.stock -= item.quantity
            db.delete(item)

        db.commit()

        return json.dumps(
            {
                "message": "Order placed successfully.",
                "order_id": order.id,
                "status": order.status,
                "total_amount": total,
            }
        )


def _user_order(db, user_id, order_id):
    return db.scalar(
        select(Order)
        .options(
            selectinload(Order.items).selectinload(OrderItem.product),
            selectinload(Order.payment),
            selectinload(Order.shipment),
        )
        .where(
            Order.id == order_id,
            Order.customer_id == user_id,
        )
    )


@tool
def get_order_history(config: RunnableConfig = None) -> str:
    """Get the authenticated user's previous orders."""
    user_id = _require_user(config)

    with SessionLocal() as db:
        orders = db.scalars(
            select(Order)
            .where(Order.customer_id == user_id)
            .order_by(Order.id.desc())
            .limit(50)
        ).all()

        return (
            json.dumps(
                [
                    {
                        "order_id": o.id,
                        "status": o.status,
                        "total_amount": float(o.total_amount),
                    }
                    for o in orders
                ]
            )
            if orders
            else "You have no previous orders."
        )


@tool
def get_order_details(
    order_id: int,
    config: RunnableConfig = None,
) -> str:
    """Get detailed information about one of the authenticated user's orders."""
    user_id = _require_user(config)

    with SessionLocal() as db:
        order = _user_order(db, user_id, order_id)

        if not order:
            return f"No order found with ID {order_id}."

        return json.dumps(
            {
                "order_id": order.id,
                "status": order.status,
                "total_amount": float(order.total_amount),
                "items": [
                    {
                        "product_id": i.product_id,
                        "name": i.product.name,
                        "quantity": i.quantity,
                        "price": float(i.price),
                    }
                    for i in order.items
                ],
            }
        )


@tool
def get_order_status(
    order_id: int,
    config: RunnableConfig = None,
) -> str:
    """Get the current status of an authenticated user's order."""
    user_id = _require_user(config)

    with SessionLocal() as db:
        order = _user_order(db, user_id, order_id)

        return (
            json.dumps(
                {
                    "order_id": order.id,
                    "status": order.status,
                }
            )
            if order
            else "Order not found."
        )


@tool
def update_order_status(
    order_id: int,
    status: str,
    config: RunnableConfig = None,
) -> str:
    """Update an order status. This operation is restricted to administrators."""
    if get_user_role(config) != "admin":
        return "Only administrators can update order status."

    with SessionLocal() as db:
        order = db.get(Order, order_id)

        if not order:
            return "Order not found."

        order.status = status
        db.commit()

        return "Order status updated."


@tool
def track_order(
    order_id: int,
    config: RunnableConfig = None,
) -> str:
    """Get shipment tracking information for an authenticated user's order."""
    user_id = _require_user(config)

    with SessionLocal() as db:
        order = _user_order(db, user_id, order_id)

        if not order:
            return "Order not found."

        if not order.shipment:
            return json.dumps(
                {
                    "order_id": order.id,
                    "shipment_status": "not_shipped",
                }
            )

        shipment = order.shipment

        return json.dumps(
            {
                "order_id": order.id,
                "tracking_number": shipment.tracking_number,
                "carrier": shipment.carrier,
                "current_location": shipment.current_location,
                "shipment_status": shipment.shipment_status,
                "estimated_delivery": (
                    shipment.estimated_delivery.isoformat()
                    if shipment.estimated_delivery
                    else None
                ),
            }
        )


@tool
def make_payment(
    order_id: int,
    method: str,
    config: RunnableConfig = None,
) -> str:
    """Process a demo payment for an authenticated user's order."""
    user_id = _require_user(config)

    with SessionLocal() as db:
        order = _user_order(db, user_id, order_id)

        if not order:
            return "Order not found."

        payment = order.payment or Payment(
            order_id=order.id,
            amount=order.total_amount,
            method=method,
            status="pending",
        )

        if payment.id is None:
            db.add(payment)

        payment.status = "successful"
        order.status = "confirmed"

        if not order.shipment:
            db.add(
                Shipment(
                    order_id=order.id,
                    tracking_number=f"SHOPORA-{order.id:06d}",
                    carrier="Shopora Logistics",
                    current_location="Processing Center",
                    shipment_status="preparing",
                    estimated_delivery=(
                        datetime.now(UTC)
                        + timedelta(days=5)
                    ),
                    updated_at=datetime.now(UTC),
                )
            )

        db.commit()

        return json.dumps(
            {
                "message": "Payment successful (demo).",
                "order_id": order.id,
                "amount": float(order.total_amount),
                "status": order.status,
            }
        )


@tool
def get_payment_status(
    order_id: int,
    config: RunnableConfig = None,
) -> str:
    """Get the payment status for an authenticated user's order."""
    user_id = _require_user(config)

    with SessionLocal() as db:
        order = _user_order(db, user_id, order_id)

        if not order:
            return "Order not found."

        return json.dumps(
            {
                "order_id": order.id,
                "payment_status": (
                    order.payment.status
                    if order.payment
                    else "not_paid"
                ),
            }
        )


@tool
def cancel_order(
    order_id: int,
    config: RunnableConfig = None,
) -> str:
    """Cancel an eligible order belonging to the authenticated user."""
    user_id = _require_user(config)

    with SessionLocal() as db:
        order = _user_order(db, user_id, order_id)

        if not order:
            return "Order not found."

        if order.status not in {"pending", "confirmed"}:
            return (
                f"Order cannot be cancelled from "
                f"status '{order.status}'."
            )

        for item in order.items:
            item.product.stock += item.quantity

        if order.payment and order.payment.status == "successful":
            order.payment.status = "refunded"

        order.status = "cancelled"

        db.commit()

        return f"Order #{order.id} has been cancelled."


@tool
def reorder(
    order_id: int,
    config: RunnableConfig = None,
) -> str:
    """Add available items from a previous order back to the authenticated user's cart."""
    user_id = _require_user(config)

    with SessionLocal() as db:
        order = _user_order(db, user_id, order_id)

        if not order:
            return "Order not found."

        for order_item in order.items:
            item = db.scalar(
                select(Cart).where(
                    Cart.customer_id == user_id,
                    Cart.product_id == order_item.product_id,
                )
            )

            qty = (
                (item.quantity if item else 0)
                + order_item.quantity
            )

            if qty <= order_item.product.stock:
                if item:
                    item.quantity = qty
                else:
                    db.add(
                        Cart(
                            customer_id=user_id,
                            thread_id=get_thread_id(config),
                            product_id=order_item.product_id,
                            quantity=order_item.quantity,
                        )
                    )

        db.commit()

        return "Available items from the order were added to your cart."


@tool
def recommend_products(
    search_term=None,
    category=None,
    max_price=None,
    min_rating=None,
    config: RunnableConfig = None,
) -> str:
    """Recommend products using personalization, filters, ratings, and product relevance."""
    user_id = get_user_id(config)

    with SessionLocal() as db:
        if user_id:
            personalized = recommend_for_user(
                db,
                db.get(Customer, user_id),
                8,
            )

            if personalized and not any(
                [
                    search_term,
                    category,
                    max_price,
                    min_rating,
                ]
            ):
                return json.dumps(
                    {
                        "recommendations": [
                            {
                                **product_to_dict(x["product"]),
                                "match_score": x["score"],
                                "reason": x["reason"],
                            }
                            for x in personalized
                        ]
                    }
                )

        products = db_filter_products(
            db,
            search_term,
            category,
            max_price=max_price,
            min_rating=min_rating,
        )

        result = []

        for product in products:
            score, reason = compute_match_score(
                product,
                max_price,
                category,
                search_term,
            )

            data = product_to_dict(product)

            data.update(
                match_score=score,
                reason=reason,
            )

            result.append(data)

        result.sort(
            key=lambda x: (
                -x["match_score"],
                -x["rating"],
            )
        )

        return json.dumps(
            {
                "recommendations": result[:8],
            }
        )


@tool
def compare_products(product_ids: list[int]) -> str:
    """Compare between 2 and 4 products using their product IDs."""
    if not 2 <= len(product_ids) <= 4:
        return "Please provide 2 to 4 product IDs."

    with SessionLocal() as db:
        products = []

        for product_id in product_ids:
            product = db.get(Product, product_id)

            if not product:
                return f"No product found with ID {product_id}."

            score, reason = compute_match_score(product)

            data = product_to_dict(product)

            data.update(
                match_score=score,
                reason=reason,
            )

            products.append(data)

        return json.dumps(
            {
                "products": products,
            }
        )


tools = [
    get_product,
    search_products,
    get_reviews,
    filter_products,
    answer_product_question,
    add_to_cart,
    view_cart,
    remove_from_cart,
    update_cart_quantity,
    checkout,
    get_order_history,
    get_order_details,
    get_order_status,
    update_order_status,
    track_order,
    make_payment,
    get_payment_status,
    cancel_order,
    reorder,
    recommend_products,
    compare_products,
]
