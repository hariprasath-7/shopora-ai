from .database import SessionLocal
from .search_service import index_products

if __name__ == "__main__":
    with SessionLocal() as db:
        print(f"Indexed {index_products(db)} products")
