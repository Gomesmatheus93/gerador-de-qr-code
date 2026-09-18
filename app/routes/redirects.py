from fastapi import APIRouter, Depends, Request
import logging
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import QRCode
from app.services.qrcodes import destination_with_utm
from app.services.security import rate_allowed
from app.services.tracking import client_ip, record_scan
from app.utils.templates import render

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/q/{slug}", include_in_schema=False)
def follow_qr(slug: str, request: Request, db: Session = Depends(get_db)):
    qr = db.scalar(select(QRCode).where(QRCode.slug == slug, QRCode.deleted_at.is_(None)))
    if qr is None:
        return render(request, "error.html", {"title": "QR Code não encontrado", "message": "Este QR Code não existe ou foi removido."}, 404)
    if not qr.active:
        return render(request, "error.html", {"title": "QR Code inativo", "message": "Este QR Code não está mais ativo."}, 410)
    destination = destination_with_utm(qr)
    ip = client_ip(request, get_settings()) or "unknown"
    if rate_allowed(f"scan:{ip}", 120, 60):
        try:
            record_scan(db, qr, request, get_settings())
        except Exception:
            db.rollback()
            logger.exception("Falha ao registrar scan para QR Code %s", qr.id)
            # A transient analytics failure must not break a printed QR Code.
    return RedirectResponse(destination, status_code=302, headers={"Cache-Control": "no-store"})
