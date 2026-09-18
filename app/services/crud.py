from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import QRCode, utcnow
from app.schemas import QRCreate, QRUpdate
from app.services.qrcodes import next_slug, short_url


def qr_dict(qr: QRCode) -> dict:
    return {key: getattr(qr, key) for key in (
        "id", "name", "slug", "destination_url", "campaign", "source", "description", "active",
        "utm_enabled", "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term",
        "created_at", "updated_at", "deleted_at"
    )} | {"short_url": short_url(qr.slug, get_settings().base_url)}


def create_qr(db: Session, data: QRCreate) -> QRCode:
    values = data.model_dump(exclude={"slug"})
    base = data.slug or data.name
    for _ in range(5):
        qr = QRCode(**values, slug=next_slug(db, base))
        db.add(qr)
        try:
            db.commit()
            db.refresh(qr)
            return qr
        except IntegrityError:
            db.rollback()
    raise HTTPException(409, "Não foi possível criar um slug exclusivo. Tente novamente.")


def update_qr(db: Session, qr: QRCode, data: QRUpdate) -> QRCode:
    if data.slug and data.slug != qr.slug:
        if not data.confirm_slug_change:
            raise HTTPException(400, "Confirme a alteração do slug: QR Codes impressos deixarão de funcionar.")
        if db.scalar(select(QRCode.id).where(QRCode.slug == data.slug, QRCode.id != qr.id)):
            raise HTTPException(409, "Este slug já está em uso.")
        qr.slug = data.slug
    for field, value in data.model_dump(exclude={"slug", "confirm_slug_change"}).items():
        setattr(qr, field, value)
    qr.updated_at = utcnow()
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Este slug já está em uso.") from exc
    db.refresh(qr)
    return qr


def soft_delete_qr(db: Session, qr: QRCode) -> None:
    qr.deleted_at = utcnow()
    qr.active = False
    db.commit()
