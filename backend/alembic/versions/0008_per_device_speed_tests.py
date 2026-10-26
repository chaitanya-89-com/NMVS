"""Add device-agent speed test jobs and measurement provenance."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0008_per_device_speed_tests"
down_revision: Union[str, Sequence[str], None] = "0007_monitoring_latency_and_health"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "device_bandwidth_history",
        sa.Column(
            "measurement_source",
            sa.String(length=32),
            nullable=False,
            server_default="legacy_backend_label",
        ),
    )
    op.create_table(
        "device_speed_test_jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ip", sa.String(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("download_mbps", sa.Float(), nullable=True),
        sa.Column("upload_mbps", sa.Float(), nullable=True),
        sa.Column("ping_ms", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_device_speed_test_jobs_id",
        "device_speed_test_jobs",
        ["id"],
        unique=False,
    )
    op.create_index(
        "ix_device_speed_test_jobs_ip",
        "device_speed_test_jobs",
        ["ip"],
        unique=False,
    )
    op.create_index(
        "ix_device_speed_test_jobs_status",
        "device_speed_test_jobs",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_device_speed_test_jobs_status", table_name="device_speed_test_jobs")
    op.drop_index("ix_device_speed_test_jobs_ip", table_name="device_speed_test_jobs")
    op.drop_index("ix_device_speed_test_jobs_id", table_name="device_speed_test_jobs")
    op.drop_table("device_speed_test_jobs")
    op.drop_column("device_bandwidth_history", "measurement_source")
