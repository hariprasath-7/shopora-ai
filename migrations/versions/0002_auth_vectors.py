"""Add user authentication, user-owned state and product embeddings."""
from alembic import op
import sqlalchemy as sa

revision = "0002_auth_vectors"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    customer_cols = {c["name"] for c in inspector.get_columns("customers")}
    if "hashed_password" not in customer_cols:
        op.add_column("customers", sa.Column("hashed_password", sa.String(255), nullable=True))
    if "role" not in customer_cols:
        op.add_column("customers", sa.Column("role", sa.String(30), nullable=False, server_default="customer"))
    if "is_active" not in customer_cols:
        op.add_column("customers", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    if "created_at" not in customer_cols:
        op.add_column("customers", sa.Column("created_at", sa.DateTime(timezone=True), nullable=True))

    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
        op.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS embedding vector(384)")
        op.execute("CREATE INDEX IF NOT EXISTS ix_products_embedding_hnsw ON products USING hnsw (embedding vector_cosine_ops)")
    else:
        if "embedding" not in {c["name"] for c in inspector.get_columns("products")}:
            op.add_column("products", sa.Column("embedding", sa.Text(), nullable=True))

    cart_cols = {c["name"] for c in inspector.get_columns("carts")}
    if "customer_id" not in cart_cols:
        op.add_column("carts", sa.Column("customer_id", sa.Integer(), nullable=True))
        op.create_index("ix_carts_customer_id", "carts", ["customer_id"])
    if "thread_id" not in cart_cols:
        op.add_column("carts", sa.Column("thread_id", sa.String(100), nullable=True))

    # Preserve existing demo data by attaching legacy state to one local account.
    op.execute("INSERT INTO customers (name, email, hashed_password, role, is_active) SELECT 'Legacy User', 'legacy@shopora.local', NULL, 'customer', TRUE WHERE NOT EXISTS (SELECT 1 FROM customers WHERE email = 'legacy@shopora.local')")
    op.execute("UPDATE carts SET customer_id = (SELECT id FROM customers WHERE email = 'legacy@shopora.local') WHERE customer_id IS NULL")

    order_cols = {c["name"] for c in inspector.get_columns("orders")}
    if "customer_id" not in order_cols:
        op.add_column("orders", sa.Column("customer_id", sa.Integer(), nullable=True))
        op.create_index("ix_orders_customer_id", "orders", ["customer_id"])
    if "thread_id" not in order_cols:
        op.add_column("orders", sa.Column("thread_id", sa.String(100), nullable=True))
    op.execute("UPDATE orders SET customer_id = (SELECT id FROM customers WHERE email = 'legacy@shopora.local') WHERE customer_id IS NULL")

    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), unique=True, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_refresh_tokens_customer_id", "refresh_tokens", ["customer_id"])
    op.create_index("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"], unique=True)


def downgrade():
    op.drop_table("refresh_tokens")
    op.drop_index("ix_orders_customer_id", table_name="orders")
    op.drop_column("orders", "customer_id")
    op.drop_index("ix_carts_customer_id", table_name="carts")
    op.drop_column("carts", "customer_id")
    op.drop_column("products", "embedding")
    op.drop_column("customers", "created_at")
    op.drop_column("customers", "is_active")
    op.drop_column("customers", "role")
    op.drop_column("customers", "hashed_password")
