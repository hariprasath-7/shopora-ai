from .database import SessionLocal
from .models import Review

reviews = [
    # Gaming Laptop
    Review(
        product_id=1,
        review_text="Excellent performance for gaming and programming. The display is sharp and responsive.",
        rating=5,
    ),
    Review(
        product_id=1,
        review_text="Very good performance for the price. Battery life could be better.",
        rating=4,
    ),
    Review(
        product_id=1,
        review_text="The laptop handles demanding games smoothly. Overall, I am very happy with it.",
        rating=5,
    ),

    # 4K Monitor
    Review(
        product_id=2,
        review_text="The 4K resolution looks fantastic and the colors are very accurate.",
        rating=5,
    ),
    Review(
        product_id=2,
        review_text="Great monitor for both productivity and entertainment.",
        rating=4,
    ),

    # Wireless Gaming Mouse
    Review(
        product_id=3,
        review_text="Very responsive mouse with excellent wireless performance.",
        rating=5,
    ),
    Review(
        product_id=3,
        review_text="Comfortable to use and the adjustable DPI is useful for gaming.",
        rating=5,
    ),
    Review(
        product_id=3,
        review_text="Good mouse overall, although the software could be improved.",
        rating=4,
    ),

    # Mechanical Keyboard
    Review(
        product_id=4,
        review_text="The mechanical switches feel great and the RGB lighting looks good.",
        rating=5,
    ),
    Review(
        product_id=4,
        review_text="Excellent keyboard for programming and gaming.",
        rating=4,
    ),

    # Bluetooth Headphones
    Review(
        product_id=5,
        review_text="The noise cancellation works very well and the sound quality is impressive.",
        rating=5,
    ),
    Review(
        product_id=5,
        review_text="Comfortable headphones with good battery life.",
        rating=4,
    ),
    Review(
        product_id=5,
        review_text="Sound quality is good, but the microphone could be better.",
        rating=4,
    ),

    # USB-C Hub
    Review(
        product_id=6,
        review_text="Very useful hub with enough ports for my laptop setup.",
        rating=4,
    ),
    Review(
        product_id=6,
        review_text="HDMI and USB ports work reliably.",
        rating=4,
    ),

    # Gaming Controller
    Review(
        product_id=7,
        review_text="The controller feels comfortable and the buttons are responsive.",
        rating=4,
    ),
    Review(
        product_id=7,
        review_text="Good controller for casual gaming.",
        rating=4,
    ),

    # Webcam
    Review(
        product_id=8,
        review_text="The video quality is clear enough for meetings and online classes.",
        rating=4,
    ),
    Review(
        product_id=8,
        review_text="Easy to set up and the built-in microphone works well.",
        rating=4,
    ),

    # Portable SSD
    Review(
        product_id=9,
        review_text="Very fast file transfers and compact enough to carry anywhere.",
        rating=5,
    ),
    Review(
        product_id=9,
        review_text="Excellent external SSD with reliable performance.",
        rating=5,
    ),

    # Wireless Bluetooth Speaker
    Review(
        product_id=10,
        review_text="Good sound quality for its size and the battery lasts a long time.",
        rating=5,
    ),
    Review(
        product_id=10,
        review_text="Portable and easy to connect. Good speaker for travel.",
        rating=4,
    ),
]


def seed_reviews():
    session = SessionLocal()

    try:
        existing_reviews = session.query(Review).count()

        if existing_reviews > 0:
            print("Reviews already exist. Skipping seed.")
            return

        session.add_all(reviews)
        session.commit()

        print(f"Successfully added {len(reviews)} reviews.")

    except Exception:
        session.rollback()
        raise

    finally:
        session.close()


if __name__ == "__main__":
    seed_reviews()