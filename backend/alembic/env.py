"""Alembic environment configuration for AMINRA Docker System.

This project uses raw SQL (asyncpg) — no SQLAlchemy ORM models.
Autogenerate is not available; all migrations are written by hand.
"""

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override sqlalchemy.url from environment variable
database_url = os.environ.get("DATABASE_URL", "")
if database_url:
    # Alembic needs a sync driver; convert asyncpg URL if present
    database_url = database_url.replace(
        "postgresql+asyncpg://", "postgresql://"
    )
    config.set_main_option("sqlalchemy.url", database_url)

# No MetaData for autogenerate — raw SQL mode
target_metadata = None


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    Generates SQL script without connecting to the database.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    Connects to the database and applies migrations directly.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
