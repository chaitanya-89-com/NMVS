"""Extend device and monitoring records with diagnostics."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0007_monitoring_latency_and_health"
down_revision: Union[str, Sequence[str], None] = "0006_one_time_reset_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("devices", sa.Column("service_port", sa.Integer(), nullable=True))
    op.add_column(
        "devices",
        sa.Column("health_check_url", sa.String(length=2048), nullable=True),
    )

    op.add_column(
        "monitoring_history",
        sa.Column("check_result", sa.String(), nullable=True),
    )
    op.add_column(
        "monitoring_history",
        sa.Column("detail", sa.String(), nullable=True),
    )
    op.add_column(
        "monitoring_history",
        sa.Column("latency_ms", sa.Float(), nullable=True),
    )
    op.add_column(
        "monitoring_history",
        sa.Column("latency_method", sa.String(length=16), nullable=True),
    )
    op.add_column(
        "monitoring_history",
        sa.Column("icmp_result", sa.String(length=16), nullable=True),
    )
    op.add_column(
        "monitoring_history",
        sa.Column("tcp_result", sa.String(length=16), nullable=True),
    )
    op.add_column(
        "monitoring_history",
        sa.Column("tcp_response_ms", sa.Float(), nullable=True),
    )
    op.add_column(
        "monitoring_history",
        sa.Column("http_status_code", sa.Integer(), nullable=True),
    )
    op.add_column(
        "monitoring_history",
        sa.Column("http_response_ms", sa.Float(), nullable=True),
    )
    op.add_column(
        "monitoring_history",
        sa.Column("http_health_status", sa.String(length=16), nullable=True),
    )
    op.create_index(
        "ix_monitoring_history_ip_checked_at",
        "monitoring_history",
        ["ip", "checked_at"],
    )
    if op.get_bind().dialect.name == "postgresql":
        op.alter_column(
            "monitoring_history",
            "checked_at",
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            postgresql_using="checked_at AT TIME ZONE 'Asia/Kolkata'",
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.alter_column(
            "monitoring_history",
            "checked_at",
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            postgresql_using="checked_at AT TIME ZONE 'Asia/Kolkata'",
        )
    op.drop_index("ix_monitoring_history_ip_checked_at", table_name="monitoring_history")
    for column in (
        "http_health_status",
        "http_response_ms",
        "http_status_code",
        "tcp_response_ms",
        "tcp_result",
        "icmp_result",
        "latency_method",
        "latency_ms",
        "detail",
        "check_result",
    ):
        op.drop_column("monitoring_history", column)
    op.drop_column("devices", "health_check_url")
    op.drop_column("devices", "service_port")
