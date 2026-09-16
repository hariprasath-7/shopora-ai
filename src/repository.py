from sqlalchemy import or_
from sqlalchemy.orm import Session

from .models import Product, Review


def get_product(session: Session, product_id: int) -> Product | None:
    """
    Retrieve a product by its ID.

    Args:
        session: Active SQLAlchemy database session.
        product_id: ID of the product to retrieve.

    Returns:
        The Product object if found, otherwise None.
    """
    return (
        session.query(Product)
        .filter(Product.id == product_id)
        .first()
    )


def search_products(
    session: Session,
    search_term: str,
) -> list[Product]:
    """
    Search products by name or description.

    Args:
        session: Active SQLAlchemy database session.
        search_term: Text to search for.

    Returns:
        A list of matching products.
    """
    search_pattern = f"%{search_term}%"

    return (
        session.query(Product)
        .filter(
            or_(
                Product.name.ilike(search_pattern),
                Product.description.ilike(search_pattern),
            )
        )
        .all()
    )


def get_reviews(
    session: Session,
    product_id: int,
) -> list[Review]:
    """
    Retrieve all reviews for a product.

    Args:
        session: Active SQLAlchemy database session.
        product_id: ID of the product.

    Returns:
        A list of reviews for the product.
    """
    return (
        session.query(Review)
        .filter(Review.product_id == product_id)
        .all()
    )


def filter_products_by_price(
    session: Session,
    min_price: float | None = None,
    max_price: float | None = None,
) -> list[Product]:
    """
    Filter products by a minimum and/or maximum price.

    Args:
        session: Active SQLAlchemy database session.
        min_price: Minimum allowed price.
        max_price: Maximum allowed price.

    Returns:
        A list of products matching the price range.
    """
    query = session.query(Product)

    if min_price is not None:
        query = query.filter(Product.price >= min_price)

    if max_price is not None:
        query = query.filter(Product.price <= max_price)

    return query.all()

def filter_products_by_category(
    session: Session,
    category: str,
) -> list[Product]:
    """
    Filter products by category.

    Args:
        session: Active SQLAlchemy database session.
        category: Product category to search for.

    Returns:
        A list of products matching the category.
    """
    return (
        session.query(Product)
        .filter(Product.category.ilike(category))
        .all()
    )

def filter_products_by_rating(
    session: Session,
    min_rating: float,
) -> list[Product]:
    """
    Filter products by minimum rating.

    Args:
        session: Active SQLAlchemy database session.
        min_rating: Minimum rating required.

    Returns:
        A list of products with ratings greater than or equal
        to the minimum rating.
    """
    return (
        session.query(Product)
        .filter(Product.rating >= min_rating)
        .all()
    )

def filter_products(
    session: Session,
    search_term: str | None = None,
    category: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    min_rating: float | None = None,
) -> list[Product]:
    """
    Filter products using multiple optional conditions.
    """

    query = session.query(Product)

    if search_term:
        search_pattern = f"%{search_term}%"
        query = query.filter(
            or_(
                Product.name.ilike(search_pattern),
                Product.description.ilike(search_pattern),
            )
        )

    if category:
        query = query.filter(Product.category.ilike(category))

    if min_price is not None:
        query = query.filter(Product.price >= min_price)

    if max_price is not None:
        query = query.filter(Product.price <= max_price)

    if min_rating is not None:
        query = query.filter(Product.rating >= min_rating)

    return query.all()