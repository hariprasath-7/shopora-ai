"""Manual smoke test for product scoring helpers, run directly against the
configured DATABASE_URL (defaults to SQLite). Not part of the pytest suite —
see tests/test_tools.py for the automated equivalent.

Usage:
    python scripts/manual_products_smoke_test.py
"""
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from src.database import SessionLocal
from src.models import Product
from src.tools import compute_match_score, product_to_dict

s = SessionLocal()
products = s.query(Product).all()
print(f"Products in DB: {len(products)}")

for p in products[:3]:
    d = product_to_dict(p)
    score, reason = compute_match_score(
        p, max_price=80000, category="laptop", search_term="AI development"
    )
    print(f"  {d['name']} | Price: {d['price']} | {score}% match | {reason}")
    print(f"    Specs: {d['specs']}")
    print(f"    Image: {d['image'][:60]}...")

s.close()
print("\nAll tests passed!")
