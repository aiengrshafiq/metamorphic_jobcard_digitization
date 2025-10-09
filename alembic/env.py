from logging.config import fileConfig
import os
from dotenv import load_dotenv

from sqlalchemy import engine_from_config, pool
from alembic import context

# Load .env
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# Import metadata/models
from app.models import Base
import app.design_v3_models  # ensure models are imported so metadata is populated

# ---- Legacy tables to ignore in autogenerate ----
LEGACY_TABLES = {
    "design_projects_v2",
    "design_stages",          # v1
    "design_projects",        # v1
    "design_tasks_v2",
    "design_tasks",           # v1
    "design_phases",
    "design_scores",
    "interdisciplinary_signoffs",
    "site_visit_logs",        # if you plan a new V3 table with same name, REMOVE this
}

def include_object(object, name, type_, reflected, compare_to):
    # prevent autogenerate from touching legacy tables
    if type_ == "table" and name in LEGACY_TABLES:
        return False
    return True

# Alembic config
config = context.config

# Logging setup
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata for autogenerate
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    # Use DATABASE_URL if present, else fall back to alembic.ini
    url = os.environ.get("DATABASE_URL") or config.get_main_option("sqlalchemy.url")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,   # <-- correct place
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # Ensure the URL is taken from .env if provided
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        config.set_main_option("sqlalchemy.url", db_url)

    # DO NOT pass include_object here — it's not an engine kwarg
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,   # <-- correct place
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
