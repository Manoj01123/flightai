"""initial schema: users, wallets, routes, bookings, agent_logs

Revision ID: 0001
Revises:
Create Date: 2026-06-14
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── users ──────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("first_name", sa.String(100), nullable=True),
        sa.Column("last_name", sa.String(100), nullable=True),
        sa.Column("booking_mode", sa.String(1), nullable=False, server_default="A"),
        sa.Column("tier", sa.String(20), nullable=False, server_default="free"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("email_verified", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("sms_notifications", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("email_notifications", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("push_notifications", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # ── wallets ─────────────────────────────────────────────────────────────
    op.create_table(
        "wallets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("balance", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_wallets_user_id", "wallets", ["user_id"], unique=True)

    # ── wallet_transactions ─────────────────────────────────────────────────
    op.create_table(
        "wallet_transactions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("wallet_id", sa.String(36), sa.ForeignKey("wallets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("transaction_type", sa.String(20), nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("stripe_payment_intent_id", sa.String(255), nullable=True),
        sa.Column("related_booking_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("idempotency_key", name="uq_wallet_txn_idempotency"),
    )
    op.create_index("ix_wallet_transactions_wallet_id", "wallet_transactions", ["wallet_id"])

    # ── routes ──────────────────────────────────────────────────────────────
    op.create_table(
        "routes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("origin", sa.String(3), nullable=False),
        sa.Column("destination", sa.String(3), nullable=False),
        sa.Column("date_from", sa.Date, nullable=False),
        sa.Column("date_to", sa.Date, nullable=False),
        sa.Column("target_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("booking_mode", sa.String(1), nullable=False, server_default="A"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("adults", sa.Integer, nullable=False, server_default="1"),
        sa.Column("cabin_class", sa.String(20), nullable=False, server_default="ECONOMY"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_routes_user_id", "routes", ["user_id"])
    op.create_index("ix_routes_user_status", "routes", ["user_id", "status"])

    # ── price_snapshots ─────────────────────────────────────────────────────
    op.create_table(
        "price_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("route_id", sa.String(36), sa.ForeignKey("routes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("airline", sa.String(10), nullable=True),
        sa.Column("flight_number", sa.String(20), nullable=True),
        sa.Column("departure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_price_snapshots_route_id", "price_snapshots", ["route_id"])
    op.create_index("ix_price_snapshots_fetched_at", "price_snapshots", ["fetched_at"])

    # ── bookings ─────────────────────────────────────────────────────────────
    op.create_table(
        "bookings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("route_id", sa.String(36), sa.ForeignKey("routes.id"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("pnr_encrypted", sa.Text, nullable=True),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("airline", sa.String(10), nullable=True),
        sa.Column("origin", sa.String(3), nullable=False),
        sa.Column("destination", sa.String(3), nullable=False),
        sa.Column("departure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("amadeus_order_id", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_bookings_user_id", "bookings", ["user_id"])

    # ── booking_attempts ──────────────────────────────────────────────────────
    op.create_table(
        "booking_attempts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("booking_id", sa.String(36), sa.ForeignKey("bookings.id"), nullable=False),
        sa.Column("fare_id", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("error_msg", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_booking_attempts_booking_id", "booking_attempts", ["booking_id"])

    # ── confirm_tokens ────────────────────────────────────────────────────────
    op.create_table(
        "confirm_tokens",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("booking_id", sa.String(36), sa.ForeignKey("bookings.id"), nullable=False),
        sa.Column("token_hash", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("token_hash", name="uq_confirm_token_hash"),
    )

    # ── agent_logs ────────────────────────────────────────────────────────────
    op.create_table(
        "agent_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("route_id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("ml_score", sa.Float, nullable=False, server_default="0"),
        sa.Column("gemini_trace_id", sa.String(255), nullable=True),
        sa.Column("reasoning", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_agent_logs_route_id", "agent_logs", ["route_id"])
    op.create_index("ix_agent_logs_user_id", "agent_logs", ["user_id"])
    op.create_index("ix_agent_logs_created_at", "agent_logs", ["created_at"])


def downgrade() -> None:
    op.drop_table("agent_logs")
    op.drop_table("confirm_tokens")
    op.drop_table("booking_attempts")
    op.drop_table("bookings")
    op.drop_table("price_snapshots")
    op.drop_table("routes")
    op.drop_table("wallet_transactions")
    op.drop_table("wallets")
    op.drop_table("users")
