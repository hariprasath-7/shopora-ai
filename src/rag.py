"""Grounded retrieval-augmented context for shopping questions."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Review
from .search_service import hybrid_search


def retrieve_context(db: Session, query: str, limit: int = 5) -> list[dict]:
    contexts: list[dict] = []
    for product, score, source in hybrid_search(db, query, limit):
        reviews = db.scalars(select(Review).where(Review.product_id == product.id).order_by(Review.rating.desc()).limit(3)).all()
        contexts.append({
            "product_id": product.id,
            "name": product.name,
            "category": product.category,
            "price": product.price,
            "rating": product.rating,
            "description": product.description,
            "retrieval_score": round(score, 4),
            "retrieval_source": source,
            "reviews": [{"rating": r.rating, "text": r.review_text} for r in reviews],
        })
    return contexts


def build_grounded_context(db: Session, query: str, limit: int = 5) -> str:
    contexts = retrieve_context(db, query, limit)
    if not contexts:
        return "No catalog evidence was found. Do not invent product facts."
    chunks = []
    for c in contexts:
        reviews = " | ".join(f"{r['rating']}/5: {r['text']}" for r in c["reviews"])
        chunks.append(
            f"PRODUCT {c['product_id']} — {c['name']} | category={c['category']} | price=₹{c['price']} | rating={c['rating']} | description={c['description']} | reviews={reviews}"
        )
    return "\n".join(chunks)
