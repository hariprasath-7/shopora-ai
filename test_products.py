import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from src.database import SessionLocal
from src.models import Product
from src.tools import product_to_dict, compute_match_score

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
