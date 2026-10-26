"""Initial baseline schema

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-10-02 10:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0001_initial_schema'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. devices table
    op.create_table(
        'devices',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('ip', sa.String(), nullable=False),
        sa.Column('device_type', sa.String(), nullable=False, server_default='Unknown Device'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('ip')
    )
    op.create_index(op.f('ix_devices_id'), 'devices', ['id'], unique=False)
    op.create_index(op.f('ix_devices_name'), 'devices', ['name'], unique=False)
    op.create_index(op.f('ix_devices_ip'), 'devices', ['ip'], unique=True)
    op.create_index(op.f('ix_devices_device_type'), 'devices', ['device_type'], unique=False)

    # 2. users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('username', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('hashed_password', sa.String(), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=True),
        sa.Column('email_verified', sa.Boolean(), server_default=sa.text('false'), nullable=True),
        sa.Column('email_otp', sa.String(), nullable=True),
        sa.Column('otp_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('username')
    )
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    # 3. alerts table
    op.create_table(
        'alerts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('device_id', sa.Integer(), nullable=True),
        sa.Column('device_name', sa.String(), nullable=True),
        sa.Column('device_ip', sa.String(), nullable=False),
        sa.Column('title', sa.String(), server_default='Device Alert', nullable=True),
        sa.Column('alert_type', sa.String(), server_default='DISCONNECTED', nullable=False),
        sa.Column('severity', sa.String(), server_default='warning', nullable=False),
        sa.Column('message', sa.String(), nullable=False),
        sa.Column('status', sa.String(), server_default='active', nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['device_id'], ['devices.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_alerts_id'), 'alerts', ['id'], unique=False)
    op.create_index(op.f('ix_alerts_device_id'), 'alerts', ['device_id'], unique=False)
    op.create_index(op.f('ix_alerts_device_ip'), 'alerts', ['device_ip'], unique=False)
    op.create_index(op.f('ix_alerts_alert_type'), 'alerts', ['alert_type'], unique=False)
    op.create_index(op.f('ix_alerts_severity'), 'alerts', ['severity'], unique=False)
    op.create_index(op.f('ix_alerts_status'), 'alerts', ['status'], unique=False)
    op.create_index(op.f('ix_alerts_created_at'), 'alerts', ['created_at'], unique=False)

    # 4. monitoring_history table
    op.create_table(
        'monitoring_history',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('ip', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('checked_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_monitoring_history_id'), 'monitoring_history', ['id'], unique=False)
    op.create_index(op.f('ix_monitoring_history_ip'), 'monitoring_history', ['ip'], unique=False)

    # 5. device_bandwidth_history table
    op.create_table(
        'device_bandwidth_history',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('ip', sa.String(), nullable=False),
        sa.Column('download_mbps', sa.Float(), nullable=True),
        sa.Column('upload_mbps', sa.Float(), nullable=True),
        sa.Column('ping_ms', sa.Float(), nullable=True),
        sa.Column('tested_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_device_bandwidth_history_id'), 'device_bandwidth_history', ['id'], unique=False)
    op.create_index(op.f('ix_device_bandwidth_history_ip'), 'device_bandwidth_history', ['ip'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_device_bandwidth_history_ip'), table_name='device_bandwidth_history')
    op.drop_index(op.f('ix_device_bandwidth_history_id'), table_name='device_bandwidth_history')
    op.drop_table('device_bandwidth_history')

    op.drop_index(op.f('ix_monitoring_history_ip'), table_name='monitoring_history')
    op.drop_index(op.f('ix_monitoring_history_id'), table_name='monitoring_history')
    op.drop_table('monitoring_history')

    op.drop_index(op.f('ix_alerts_status'), table_name='alerts')
    op.drop_index(op.f('ix_alerts_severity'), table_name='alerts')
    op.drop_index(op.f('ix_alerts_id'), table_name='alerts')
    op.drop_index(op.f('ix_alerts_device_ip'), table_name='alerts')
    op.drop_index(op.f('ix_alerts_device_id'), table_name='alerts')
    op.drop_index(op.f('ix_alerts_created_at'), table_name='alerts')
    op.drop_index(op.f('ix_alerts_alert_type'), table_name='alerts')
    op.drop_table('alerts')

    op.drop_index(op.f('ix_users_username'), table_name='users')
    op.drop_index(op.f('ix_users_id'), table_name='users')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')

    op.drop_index(op.f('ix_devices_device_type'), table_name='devices')
    op.drop_index(op.f('ix_devices_name'), table_name='devices')
    op.drop_index(op.f('ix_devices_ip'), table_name='devices')
    op.drop_index(op.f('ix_devices_id'), table_name='devices')
    op.drop_table('devices')
