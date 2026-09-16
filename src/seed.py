from .database import SessionLocal
from .models import Product

products = [
    Product(
        name="Gaming Laptop",
        description="High-performance laptop with a powerful processor and dedicated graphics for gaming and development.",
        category="Laptop",
        price=74999,
        rating=4.6,
        stock=10,
    ),
    Product(
        name="4K Monitor",
        description="27-inch 4K UHD monitor with sharp visuals, wide viewing angles, and excellent color reproduction.",
        category="Monitor",
        price=32999,
        rating=4.5,
        stock=15,
    ),
    Product(
        name="Wireless Gaming Mouse",
        description="Low-latency wireless gaming mouse with adjustable DPI and ergonomic design.",
        category="Mouse",
        price=1899,
        rating=4.7,
        stock=25,
    ),
    Product(
        name="Mechanical Keyboard",
        description="RGB mechanical keyboard with tactile switches designed for gaming and programming.",
        category="Keyboard",
        price=3499,
        rating=4.5,
        stock=20,
    ),
    Product(
        name="Bluetooth Headphones",
        description="Wireless over-ear headphones with active noise cancellation and long battery life.",
        category="Headphones",
        price=5999,
        rating=4.4,
        stock=12,
    ),
    Product(
        name="USB-C Hub",
        description="Multi-port USB-C hub with HDMI, USB 3.0, and SD card support.",
        category="Accessories",
        price=2499,
        rating=4.3,
        stock=30,
    ),
    Product(
        name="Gaming Controller",
        description="Wireless gaming controller with ergonomic grips and responsive buttons.",
        category="Gaming",
        price=2799,
        rating=4.2,
        stock=18,
    ),
    Product(
        name="Webcam",
        description="Full HD webcam with built-in microphone suitable for meetings, streaming, and online classes.",
        category="Camera",
        price=2999,
        rating=4.1,
        stock=22,
    ),
    Product(
        name="Portable SSD",
        description="Fast external SSD with USB-C connectivity for backups, file transfers, and portable storage.",
        category="Storage",
        price=6499,
        rating=4.8,
        stock=14,
    ),
    Product(
        name="Wireless Bluetooth Speaker",
        description="Compact portable speaker with rich sound, Bluetooth connectivity, and long battery life.",
        category="Speaker",
        price=3999,
        rating=4.6,
        stock=16,
    ),
]


def seed_products():
    session = SessionLocal()

    try:
        existing_products = session.query(Product).count()

        if existing_products > 0:
            print("Products already exist. Skipping seed.")
            return

        session.add_all(products)
        session.commit()

        print(f"Successfully added {len(products)} products.")

    except Exception:
        session.rollback()
        raise

    finally:
        session.close()


if __name__ == "__main__":
    seed_products()