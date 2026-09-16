from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base

try:
    from pgvector.sqlalchemy import Vector
except ImportError:  # pragma: no cover
    Vector = None


class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(30), nullable=False, default="customer", server_default="customer")
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    orders: Mapped[list[Order]] = relationship(back_populates="customer")
    refresh_tokens: Mapped[list[RefreshToken]] = relationship(back_populates="customer", cascade="all, delete-orphan")


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("price >= 0", name="ck_products_price_nonnegative"),
        CheckConstraint("rating >= 0 AND rating <= 5", name="ck_products_rating_range"),
        CheckConstraint("stock >= 0", name="ck_products_stock_nonnegative"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    rating: Mapped[float] = mapped_column(Float, nullable=False)
    stock: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(384) if Vector else Text, nullable=True)
    reviews: Mapped[list[Review]] = relationship(back_populates="product", cascade="all, delete-orphan")
    cart_items: Mapped[list[Cart]] = relationship(back_populates="product")
    order_items: Mapped[list[OrderItem]] = relationship(back_populates="product")


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (CheckConstraint("rating >= 1 AND rating <= 5", name="ck_reviews_rating_range"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    review_text: Mapped[str] = mapped_column(Text, nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    product: Mapped[Product] = relationship(back_populates="reviews")


class Cart(Base):
    __tablename__ = "carts"
    __table_args__ = (
        UniqueConstraint("customer_id", "product_id", name="uq_cart_customer_product"),
        CheckConstraint("quantity > 0", name="ck_carts_quantity_positive"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True)
    thread_id: Mapped[str | None] = mapped_column(String(100), index=True, nullable=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    product: Mapped[Product] = relationship(back_populates="cart_items")


class Order(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True)
    thread_id: Mapped[str | None] = mapped_column(String(100), index=True, nullable=True)
    total_amount: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    customer: Mapped[Customer] = relationship(back_populates="orders")
    items: Mapped[list[OrderItem]] = relationship(back_populates="order", cascade="all, delete-orphan")
    payment: Mapped[Payment | None] = relationship(back_populates="order", uselist=False, cascade="all, delete-orphan")
    shipment: Mapped[Shipment | None] = relationship(back_populates="order", uselist=False, cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_order_items_quantity_positive"),
        CheckConstraint("price >= 0", name="ck_order_items_price_nonnegative"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    order: Mapped[Order] = relationship(back_populates="items")
    product: Mapped[Product] = relationship(back_populates="order_items")


class Payment(Base):
    __tablename__ = "payments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, unique=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    method: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    order: Mapped[Order] = relationship(back_populates="payment")


class Shipment(Base):
    __tablename__ = "shipments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, unique=True)
    tracking_number: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    carrier: Mapped[str] = mapped_column(String(100), nullable=False)
    current_location: Mapped[str] = mapped_column(String(200), nullable=False)
    shipment_status: Mapped[str] = mapped_column(String(50), default="preparing", nullable=False)
    estimated_delivery: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC), nullable=False)
    order: Mapped[Order] = relationship(back_populates="shipment")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    customer: Mapped[Customer] = relationship(back_populates="refresh_tokens")
