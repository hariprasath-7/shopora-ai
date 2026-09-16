"""initial shopora schema

Revision ID: 0001_initial
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("customers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("email", sa.String(200), nullable=False),
        sa.Column("phone", sa.String(20)),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_customers_email", "customers", ["email"], unique=True)

    op.create_table("products",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("rating", sa.Float(), nullable=False),
        sa.Column("stock", sa.Integer(), nullable=False),
    )
    op.create_index("ix_products_category", "products", ["category"])

    op.create_table("reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("review_text", sa.Text(), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
    )
    op.create_index("ix_reviews_product_id", "reviews", ["product_id"])

    op.create_table("carts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("thread_id", sa.String(100), nullable=False),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("thread_id", "product_id", name="uq_cart_thread_product"),
    )
    op.create_index("ix_carts_thread_id", "carts", ["thread_id"])

    op.create_table("orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("thread_id", sa.String(100), nullable=False),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id")),
        sa.Column("total_amount", sa.Float(), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
    )
    op.create_index("ix_orders_thread_id", "orders", ["thread_id"])

    op.create_table("order_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
    )

    op.create_table("payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("method", sa.String(50), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.UniqueConstraint("order_id"),
    )

    op.create_table("shipments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("tracking_number", sa.String(100), nullable=False),
        sa.Column("carrier", sa.String(100), nullable=False),
        sa.Column("current_location", sa.String(200), nullable=False),
        sa.Column("shipment_status", sa.String(50), nullable=False, server_default="preparing"),
        sa.Column("estimated_delivery", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("order_id"),
        sa.UniqueConstraint("tracking_number"),
    )
    op.create_index("ix_shipments_tracking_number", "shipments", ["tracking_number"], unique=True)


def downgrade():
    op.drop_table("shipments")
    op.drop_table("payments")
    op.drop_table("order_items")
    op.drop_index("ix_orders_thread_id", table_name="orders")
    op.drop_table("orders")
    op.drop_index("ix_carts_thread_id", table_name="carts")
    op.drop_table("carts")
    op.drop_index("ix_reviews_product_id", table_name="reviews")
    op.drop_table("reviews")
    op.drop_index("ix_products_category", table_name="products")
    op.drop_table("products")
    op.drop_index("ix_customers_email", table_name="customers")
    op.drop_table("customers")
