"""Personalized recommendation scoring using purchases + product quality."""
from __future__ import annotations

from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Customer, Order, Product


def recommend_for_user(db: Session, user: Customer, limit: int = 8) -> list[dict]:
    orders = db.scalars(select(Order).where(Order.customer_id == user.id)).all()
    items = []
    for order in orders:
        items.extend(order.items)
    bought_ids = {item.product_id for item in items}
    category_counts = Counter(item.product.category for item in items if item.product)
    favorite_categories = {c for c, _ in category_counts.most_common(3)}

    products = db.scalars(select(Product).where(Product.stock > 0)).all()
    scored = []
    for product in products:
        if product.id in bought_ids:
            continue
        category_score = 1.0 if product.category in favorite_categories else 0.0
        quality_score = product.rating / 5
        value_score = 1.0 / (1.0 + product.price / 100000)
        score = 0.55 * category_score + 0.30 * quality_score + 0.15 * value_score
        reason = "Popular high-rated product"
        if category_score:
            reason = f"Based on your interest in {product.category} products"
        scored.append((product, score, reason))
    scored.sort(key=lambda x: x[1], reverse=True)
    return [{"product": p, "score": round(s * 100), "reason": r} for p, s, r in scored[:limit]]
