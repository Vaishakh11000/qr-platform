from logging.config import fileConfig
from pathlib import Path
import sys

from alembic import context
from sqlalchemy import create_engine, pool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings
from app.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def include_name(name, type_, parent_names):
    if type_ == "schema":
        return name == "app"

    if type_ == "table":
        return (
            parent_names.get("schema_name") == "app"
            and name != "alembic_version"
        )

    return True


def run_migrations_offline():
    context.configure(
        url=settings.database_url.render_as_string(hide_password=False),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        include_name=include_name,
        version_table="alembic_version",
        version_table_schema="app",
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.execute("CREATE SCHEMA IF NOT EXISTS app")
        context.run_migrations()


def run_migrations_online():
    connectable = create_engine(
        settings.database_url,
        poolclass=pool.NullPool,
    )

    try:
        with connectable.connect() as connection:
            connection.exec_driver_sql("CREATE SCHEMA IF NOT EXISTS app")
            connection.commit()
            connection.exec_driver_sql("SET search_path TO public")
            connection.dialect.default_schema_name = "public"
            connection.commit()

            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                include_schemas=True,
                include_name=include_name,
                version_table="alembic_version",
                version_table_schema="app",
                compare_type=True,
                compare_server_default=True,
            )

            with context.begin_transaction():
                context.run_migrations()
    finally:
        connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
