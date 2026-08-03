import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context
from dotenv import load_dotenv

load_dotenv()

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Wire in all models so Alembic can autogenerate
from services.shared.database import Base  # noqa: E402
import services.user.models  # noqa: F401, E402
import services.wallet.models  # noqa: F401, E402
import services.booking.models  # noqa: F401, E402
import services.orchestrator.models  # noqa: F401, E402

target_metadata = Base.metadata

# Override sqlalchemy.url from DATABASE_URL env var if set
db_url = os.environ.get("DATABASE_URL", "")
if db_url:
    # Alembic needs sync driver — replace asyncpg with psycopg2
    sync_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    config.set_main_option("sqlalchemy.url", sync_url)


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
