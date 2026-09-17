"""Development-only database bootstrap.

Production deployments should use `alembic upgrade head` instead of create_all().
"""
from src import models
from src.database import Base, engine

if __name__ == "__main__":
    Base.metadata.create_all(engine)
    print("Development database tables created.")
