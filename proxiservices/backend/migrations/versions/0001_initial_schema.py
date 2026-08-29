"""schema initial ProxiServices

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-08-29

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "proxiservices"


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")

    user_role = postgresql.ENUM("client", "provider", "admin", name="user_role", schema=SCHEMA)
    kyc_status = postgresql.ENUM("unverified", "pending", "approved", "rejected", name="kyc_status", schema=SCHEMA)
    mission_status = postgresql.ENUM(
        "open", "quoted", "accepted", "in_progress", "completed", "disputed", "cancelled",
        name="mission_status", schema=SCHEMA,
    )
    quote_status = postgresql.ENUM("pending", "accepted", "rejected", name="quote_status", schema=SCHEMA)
    transaction_status = postgresql.ENUM(
        "pending", "held_in_escrow", "released", "refunded", "failed", name="transaction_status", schema=SCHEMA,
    )
    subscription_plan = postgresql.ENUM("free", "pro", name="subscription_plan", schema=SCHEMA)
    subscription_status = postgresql.ENUM("active", "expired", "cancelled", name="subscription_status", schema=SCHEMA)
    boost_target_type = postgresql.ENUM("mission", "provider_profile", name="boost_target_type", schema=SCHEMA)
    boost_status = postgresql.ENUM("pending_payment", "active", "expired", name="boost_status", schema=SCHEMA)

    # Chaque type ENUM est créé automatiquement par SQLAlchemy lors de la création
    # de la première (et unique) table qui l'utilise — inutile de les créer ici.

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("phone", sa.String(30), unique=True, nullable=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(150), nullable=False),
        sa.Column("role", user_role, nullable=False, server_default="client"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_verified_provider", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("kyc_status", kyc_status, nullable=False, server_default="unverified"),
        sa.Column("kyc_document_path", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema=SCHEMA,
    )

    op.create_table(
        "service_categories",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(100), unique=True, nullable=False),
        sa.Column("slug", sa.String(100), unique=True, nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        schema=SCHEMA,
    )

    op.create_table(
        "missions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("client_id", sa.Uuid(), sa.ForeignKey(f"{SCHEMA}.users.id"), nullable=False),
        sa.Column("provider_id", sa.Uuid(), sa.ForeignKey(f"{SCHEMA}.users.id"), nullable=True),
        sa.Column("category_id", sa.Uuid(), sa.ForeignKey(f"{SCHEMA}.service_categories.id"), nullable=False),
        sa.Column("title", sa.String(150), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("budget_fcfa", sa.Integer(), nullable=False),
        sa.Column("neighborhood", sa.String(150), nullable=False),
        sa.Column("latitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("longitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("status", mission_status, nullable=False, server_default="open"),
        sa.Column("dispute_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema=SCHEMA,
    )

    op.create_table(
        "quotes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("mission_id", sa.Uuid(), sa.ForeignKey(f"{SCHEMA}.missions.id"), nullable=False),
        sa.Column("provider_id", sa.Uuid(), sa.ForeignKey(f"{SCHEMA}.users.id"), nullable=False),
        sa.Column("amount_fcfa", sa.Integer(), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("status", quote_status, nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema=SCHEMA,
    )

    op.create_table(
        "transactions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("mission_id", sa.Uuid(), sa.ForeignKey(f"{SCHEMA}.missions.id"), nullable=False),
        sa.Column("client_id", sa.Uuid(), sa.ForeignKey(f"{SCHEMA}.users.id"), nullable=False),
        sa.Column("provider_id", sa.Uuid(), sa.ForeignKey(f"{SCHEMA}.users.id"), nullable=False),
        sa.Column("amount_fcfa", sa.Integer(), nullable=False),
        sa.Column("commission_fcfa", sa.Integer(), nullable=False),
        sa.Column("status", transaction_status, nullable=False, server_default="pending"),
        sa.Column("paydunia_reference", sa.String(150), unique=True, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema=SCHEMA,
    )

    op.create_table(
        "provider_subscriptions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("provider_id", sa.Uuid(), sa.ForeignKey(f"{SCHEMA}.users.id"), unique=True, nullable=False),
        sa.Column("plan", subscription_plan, nullable=False, server_default="free"),
        sa.Column("status", subscription_status, nullable=False, server_default="active"),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        schema=SCHEMA,
    )

    op.create_table(
        "boosts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("owner_id", sa.Uuid(), sa.ForeignKey(f"{SCHEMA}.users.id"), nullable=False),
        sa.Column("target_type", boost_target_type, nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("amount_fcfa", sa.Integer(), nullable=False),
        sa.Column("status", boost_status, nullable=False, server_default="pending_payment"),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        schema=SCHEMA,
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey(f"{SCHEMA}.users.id"), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("target_type", sa.String(100), nullable=False),
        sa.Column("target_id", sa.String(100), nullable=False),
        sa.Column("extra_data", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema=SCHEMA,
    )

    for table in (
        "users", "service_categories", "missions", "quotes",
        "transactions", "provider_subscriptions", "boosts", "audit_logs",
    ):
        op.execute(f"ALTER TABLE {SCHEMA}.{table} ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    for table in (
        "audit_logs", "boosts", "provider_subscriptions", "transactions",
        "quotes", "missions", "service_categories", "users",
    ):
        op.drop_table(table, schema=SCHEMA)

    for enum_name in (
        "boost_status", "boost_target_type", "subscription_status", "subscription_plan",
        "transaction_status", "quote_status", "mission_status", "kyc_status", "user_role",
    ):
        postgresql.ENUM(name=enum_name, schema=SCHEMA).drop(op.get_bind(), checkfirst=True)

    # Le schema lui-même n'est pas supprimé : il continue d'héberger la table
    # alembic_version (voir version_table_schema dans migrations/env.py).
