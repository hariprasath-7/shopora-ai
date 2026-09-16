"""Hybrid lexical + semantic product retrieval."""
from __future__ import annotations

from functools import lru_cache

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .config import settings
from .models import Product


@lru_cache(maxsize=1)
def get_embedding_model():
    if not settings.semantic_search_enabled:
        return None
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(settings.embedding_model)


def product_text(product: Product) -> str:
    return f"{product.name}. Category: {product.category}. {product.description}"


def embed_text(text: str) -> list[float]:
    model = get_embedding_model()
    if model is None:
        return []
    vector = model.encode(text, normalize_embeddings=True)
    return vector.tolist()


def index_products(db: Session, batch_size: int = 32) -> int:
    """Create/update embeddings. Requires PostgreSQL + pgvector for persistence."""
    if not settings.database_url.startswith("postgres"):
        return 0
    products = db.scalars(select(Product).order_by(Product.id)).all()
    model = get_embedding_model()
    if model is None:
        return 0
    texts = [product_text(p) for p in products]
    vectors = model.encode(texts, batch_size=batch_size, normalize_embeddings=True, show_progress_bar=False)
    for product, vector in zip(products, vectors):
        product.embedding = vector.tolist()
    db.commit()
    return len(products)


def hybrid_search(db: Session, query: str, limit: int = 12) -> list[tuple[Product, float, str]]:
    query = query.strip()
    if not query:
        return [(p, 0.0, "catalog") for p in db.scalars(select(Product).order_by(Product.rating.desc()).limit(limit)).all()]

    lexical_stmt = select(Product).where(or_(Product.name.ilike(f"%{query}%"), Product.description.ilike(f"%{query}%"), Product.category.ilike(f"%{query}%")))
    lexical = db.scalars(lexical_stmt.limit(max(limit * 3, 20))).all()
    lexical_rank = {p.id: 1.0 - (i / max(len(lexical), 1)) for i, p in enumerate(lexical)}

    if settings.database_url.startswith("postgres") and settings.semantic_search_enabled:
        try:
            qvec = embed_text(query)
            distance = Product.embedding.cosine_distance(qvec)
            semantic_rows = db.execute(select(Product, distance.label("distance")).where(Product.embedding.is_not(None)).order_by(distance).limit(limit * 3)).all()
            semantic_rank = {p.id: 1.0 / (1.0 + float(distance)) for p, distance in semantic_rows}
        except Exception:
            semantic_rank = {}
    else:
        semantic_rank = {}

    candidates = {p.id: p for p in lexical}
    for p, _distance in semantic_rows if 'semantic_rows' in locals() else []:
        candidates[p.id] = p

    scored = []
    for pid, product in candidates.items():
        score = 0.55 * semantic_rank.get(pid, 0.0) + 0.35 * lexical_rank.get(pid, 0.0) + 0.10 * (product.rating / 5)
        source = "hybrid" if pid in semantic_rank and pid in lexical_rank else ("semantic" if pid in semantic_rank else "lexical")
        scored.append((product, score, source))
    scored.sort(key=lambda row: row[1], reverse=True)
    return scored[:limit]
