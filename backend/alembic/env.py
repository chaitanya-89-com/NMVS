import os
import sys
from logging.config import fileConfig
from app.settings.model import UserSettings

from alembic import context

# Ensure the backend root directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import Base and engine/DATABASE_URL from our application
from database.database import Base, DATABASE_URL, engine

# Import all SQLAlchemy models to register them on Base.metadata
from app.users.model import User
from app.devices.model import Device
from app.alerts.model import Alert
from app.monitoring.model import MonitoringHistory
from app.speed_monitoring.model import (
    AgentDiscoveredNetwork,
    DeviceBandwidthHistory,
    DeviceSpeedTestJob,
)

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# target metadata for 'autogenerate' support
target_metadata = Base.metadata

# Keep config sqlalchemy.url synchronized with dynamic DATABASE_URL
database_url_str = DATABASE_URL.render_as_string(hide_password=False)
config.set_main_option("sqlalchemy.url", database_url_str.replace("%", "%%"))


def include_object(object, name, type_, reflected, compare_to):
    if type_ == "table" and reflected and compare_to is None:
        return False
    return True


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            include_object=include_object,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
