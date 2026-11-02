"""Add Bakong KHQR payment tables and columns.

Revision ID: 0001_bakong_khqr
Revises: None
Create Date: 2026-11-02
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_bakong_khqr"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Extend existing `payments` table with Bakong KHQR columns
    with op.batch_alter_table("payments") as batch_op:
        batch_op.add_column(sa.Column("currency", sa.String(length=3), nullable=False, server_default="USD"))
        batch_op.add_column(sa.Column("qr_string", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("qr_md5", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("deeplink_url", sa.String(length=512), nullable=True))
        batch_op.add_column(sa.Column("expires_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("paid_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("bakong_transaction_hash", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("payer_account_masked", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("receiver_account", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="1"))
        batch_op.create_index("ix_payments_qr_md5", ["qr_md5"], unique=True)
        batch_op.create_index("ix_payments_bakong_tx_hash", ["bakong_transaction_hash"], unique=True)

    # 2. `payment_attempts` table
    op.create_table(
        "payment_attempts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("payment_id", sa.Integer(), sa.ForeignKey("payments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="USD"),
        sa.Column("qr_string", sa.Text(), nullable=False),
        sa.Column("qr_md5", sa.String(length=32), nullable=False),
        sa.Column("deeplink_url", sa.String(length=512), nullable=True),
        sa.Column("bill_number", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="pending"),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("paid_at", sa.DateTime(), nullable=True),
        sa.Column("bakong_transaction_hash", sa.String(length=128), nullable=True),
        sa.Column("payer_account_masked", sa.String(length=64), nullable=True),
        sa.Column("raw_bakong_response", sa.Text(), nullable=True),
        sa.Column("failure_reason", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("payment_id", "attempt_number", name="uq_payment_attempt_number"),
        sa.UniqueConstraint("qr_md5", name="uq_payment_attempts_qr_md5"),
        sa.UniqueConstraint("bakong_transaction_hash", name="uq_payment_attempts_tx_hash"),
    )
    op.create_index("ix_payment_attempts_order_id", "payment_attempts", ["order_id"])

    # 3. `payment_events` immutable audit log table
    op.create_table(
        "payment_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("payment_id", sa.Integer(), sa.ForeignKey("payments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("previous_status", sa.String(length=24), nullable=True),
        sa.Column("new_status", sa.String(length=24), nullable=True),
        sa.Column("qr_md5", sa.String(length=32), nullable=True),
        sa.Column("actor", sa.String(length=64), nullable=False, server_default="system"),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_payment_events_payment_id", "payment_events", ["payment_id"])
    op.create_index("ix_payment_events_order_id", "payment_events", ["order_id"])

    # 4. `refunds` table
    op.create_table(
        "refunds",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("payment_id", sa.Integer(), sa.ForeignKey("payments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="USD"),
        sa.Column("reason", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="pending_manual"),
        sa.Column("external_refund_ref", sa.String(length=128), nullable=True),
        sa.Column("processed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("refunded_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_refunds_order_id", "refunds", ["order_id"])

    # 5. `idempotency_keys` table
    op.create_table(
        "idempotency_keys",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("idempotency_key", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("endpoint", sa.String(length=128), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=False),
        sa.Column("response_body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", "user_id", "endpoint", name="uq_idempotency_key_user_endpoint"),
    )

    # 6. `verification_jobs` queue table for PostgreSQL FOR UPDATE SKIP LOCKED worker
    op.create_table(
        "verification_jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("payment_id", sa.Integer(), sa.ForeignKey("payments.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "attempt_id",
            sa.Integer(),
            sa.ForeignKey("payment_attempts.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("qr_md5", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="queued"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="40"),
        sa.Column("next_run_at", sa.DateTime(), nullable=False),
        sa.Column("locked_at", sa.DateTime(), nullable=True),
        sa.Column("locked_by", sa.String(length=64), nullable=True),
        sa.Column("last_error", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("qr_md5", name="uq_verification_jobs_qr_md5"),
    )
    op.create_index("ix_verification_jobs_status_next_run", "verification_jobs", ["status", "next_run_at"])


def downgrade() -> None:
    op.drop_index("ix_verification_jobs_status_next_run", table_name="verification_jobs")
    op.drop_table("verification_jobs")
    op.drop_table("idempotency_keys")
    op.drop_index("ix_refunds_order_id", table_name="refunds")
    op.drop_table("refunds")
    op.drop_index("ix_payment_events_order_id", table_name="payment_events")
    op.drop_index("ix_payment_events_payment_id", table_name="payment_events")
    op.drop_table("payment_events")
    op.drop_index("ix_payment_attempts_order_id", table_name="payment_attempts")
    op.drop_table("payment_attempts")

    with op.batch_alter_table("payments") as batch_op:
        batch_op.drop_index("ix_payments_bakong_tx_hash")
        batch_op.drop_index("ix_payments_qr_md5")
        batch_op.drop_column("attempt_count")
        batch_op.drop_column("receiver_account")
        batch_op.drop_column("payer_account_masked")
        batch_op.drop_column("bakong_transaction_hash")
        batch_op.drop_column("paid_at")
        batch_op.drop_column("expires_at")
        batch_op.drop_column("deeplink_url")
        batch_op.drop_column("qr_md5")
        batch_op.drop_column("qr_string")
        batch_op.drop_column("currency")
