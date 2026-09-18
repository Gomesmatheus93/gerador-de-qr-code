from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class QRCode(Base):
    __tablename__ = "qr_codes"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(180))
    slug: Mapped[str] = mapped_column(String(220), unique=True, index=True)
    destination_url: Mapped[str] = mapped_column(Text)
    campaign: Mapped[str | None] = mapped_column(String(180), index=True)
    source: Mapped[str | None] = mapped_column(String(180))
    description: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    utm_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    utm_source: Mapped[str | None] = mapped_column(String(255))
    utm_medium: Mapped[str | None] = mapped_column(String(255))
    utm_campaign: Mapped[str | None] = mapped_column(String(255))
    utm_content: Mapped[str | None] = mapped_column(String(255))
    utm_term: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime)
    scans: Mapped[list["QRScan"]] = relationship(back_populates="qr_code")


class QRScan(Base):
    __tablename__ = "qr_scans"
    __table_args__ = (
        Index("ix_qr_scans_qr_scanned", "qr_code_id", "scanned_at"),
        Index("ix_qr_scans_session_scanned", "session_hash", "scanned_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    qr_code_id: Mapped[int] = mapped_column(ForeignKey("qr_codes.id", ondelete="RESTRICT"), index=True)
    scanned_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    ip: Mapped[str | None] = mapped_column(String(64))
    ip_hash: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(Text)
    browser: Mapped[str | None] = mapped_column(String(80))
    operating_system: Mapped[str | None] = mapped_column(String(80))
    device_type: Mapped[str | None] = mapped_column(String(30))
    referer: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(String(100))
    country: Mapped[str | None] = mapped_column(String(120))
    region: Mapped[str | None] = mapped_column(String(120))
    city: Mapped[str | None] = mapped_column(String(120))
    is_unique_scan: Mapped[bool] = mapped_column(Boolean, default=True)
    session_hash: Mapped[str] = mapped_column(String(64))
    qr_code: Mapped[QRCode] = relationship(back_populates="scans")
