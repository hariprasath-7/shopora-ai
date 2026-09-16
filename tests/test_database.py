import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database import Base
from src.models import (
    Product,
    Review,
)
from src.repository import (
    filter_products,
    filter_products_by_category,
    filter_products_by_price,
    filter_products_by_rating,
    get_product,
    get_reviews,
    search_products,
)


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database session for testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Seed sample products
    p1 = Product(
        name="Test Gaming Laptop",
        description="High performance gaming laptop with fast GPU",
        category="Laptop",
        price=75000.0,
        rating=4.8,
        stock=10,
    )
    p2 = Product(
        name="Test Wireless Mouse",
        description="Ergonomic wireless mouse with high precision DPI",
        category="Mouse",
        price=1500.0,
        rating=4.5,
        stock=20,
    )
    session.add_all([p1, p2])
    session.commit()

    yield session

    session.close()


def test_get_product(db_session):
    p = get_product(db_session, 1)
    assert p is not None
    assert p.name == "Test Gaming Laptop"
    assert p.price == 75000.0


def test_search_products(db_session):
    results = search_products(db_session, "laptop")
    assert len(results) == 1
    assert results[0].id == 1

    results_empty = search_products(db_session, "nonexistent")
    assert len(results_empty) == 0


def test_filter_products(db_session):
    results = filter_products(
        db_session,
        search_term="mouse",
        category="Mouse",
        max_price=2000.0,
        min_rating=4.0,
    )
    assert len(results) == 1
    assert results[0].name == "Test Wireless Mouse"


def test_filter_by_price(db_session):
    affordable = filter_products_by_price(db_session, max_price=5000.0)
    assert len(affordable) == 1
    assert affordable[0].name == "Test Wireless Mouse"


def test_filter_by_category(db_session):
    laptops = filter_products_by_category(db_session, "Laptop")
    assert len(laptops) == 1
    assert laptops[0].category == "Laptop"


def test_filter_by_rating(db_session):
    high_rated = filter_products_by_rating(db_session, min_rating=4.7)
    assert len(high_rated) == 1
    assert high_rated[0].name == "Test Gaming Laptop"


def test_reviews_relationship(db_session):
    p = get_product(db_session, 1)
    r = Review(product_id=p.id, review_text="Great laptop!", rating=5)
    db_session.add(r)
    db_session.commit()

    reviews = get_reviews(db_session, p.id)
    assert len(reviews) == 1
    assert reviews[0].review_text == "Great laptop!"
    assert reviews[0].rating == 5
