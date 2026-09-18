"""Initial users, QR codes and scans.

Revision ID: 0001_initial
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_table(
        "qr_codes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("slug", sa.String(length=220), nullable=False),
        sa.Column("destination_url", sa.Text(), nullable=False),
        sa.Column("campaign", sa.String(length=180)),
        sa.Column("source", sa.String(length=180)),
        sa.Column("description", sa.Text()),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("utm_enabled", sa.Boolean(), nullable=False),
        sa.Column("utm_source", sa.String(length=255)),
        sa.Column("utm_medium", sa.String(length=255)),
        sa.Column("utm_campaign", sa.String(length=255)),
        sa.Column("utm_content", sa.String(length=255)),
        sa.Column("utm_term", sa.String(length=255)),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime()),
    )
    op.create_index("ix_qr_codes_slug", "qr_codes", ["slug"], unique=True)
    op.create_index("ix_qr_codes_campaign", "qr_codes", ["campaign"])
    op.create_table(
        "qr_scans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("qr_code_id", sa.Integer(), sa.ForeignKey("qr_codes.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("scanned_at", sa.DateTime(), nullable=False),
        sa.Column("ip", sa.String(length=64)),
        sa.Column("ip_hash", sa.String(length=64)),
        sa.Column("user_agent", sa.Text()),
        sa.Column("browser", sa.String(length=80)),
        sa.Column("operating_system", sa.String(length=80)),
        sa.Column("device_type", sa.String(length=30)),
        sa.Column("referer", sa.Text()),
        sa.Column("language", sa.String(length=100)),
        sa.Column("country", sa.String(length=120)),
        sa.Column("region", sa.String(length=120)),
        sa.Column("city", sa.String(length=120)),
        sa.Column("is_unique_scan", sa.Boolean(), nullable=False),
        sa.Column("session_hash", sa.String(length=64), nullable=False),
    )
    op.create_index("ix_qr_scans_qr_code_id", "qr_scans", ["qr_code_id"])
    op.create_index("ix_qr_scans_scanned_at", "qr_scans", ["scanned_at"])
    op.create_index("ix_qr_scans_qr_scanned", "qr_scans", ["qr_code_id", "scanned_at"])
    op.create_index("ix_qr_scans_session_scanned", "qr_scans", ["session_hash", "scanned_at"])


def downgrade():
    op.drop_table("qr_scans")
    op.drop_table("qr_codes")
    op.drop_table("users")
