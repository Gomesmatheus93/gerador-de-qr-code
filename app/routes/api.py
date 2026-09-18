from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import QRCode, QRScan, User
from app.schemas import QRCreate, QROut, QRUpdate
from app.services.crud import create_qr, qr_dict, soft_delete_qr, update_qr
from app.services.qrcodes import get_qr_or_404
from app.services.security import api_user
from app.services.stats import dashboard_stats, qr_stats

router = APIRouter(prefix="/api", tags=["Admin API"], dependencies=[Depends(api_user)])


@router.get("/qrcodes")
def list_qrcodes(db: Session = Depends(get_db), page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), search: str = "", status: str = "all", campaign: str = ""):
    stmt = select(QRCode).where(QRCode.deleted_at.is_(None))
    if search:
        pattern = f"%{search.strip()}%"
        stmt = stmt.where(or_(QRCode.name.ilike(pattern), QRCode.slug.ilike(pattern), QRCode.campaign.ilike(pattern), QRCode.destination_url.ilike(pattern)))
    if status in ("active", "inactive"):
        stmt = stmt.where(QRCode.active.is_(status == "active"))
    if campaign:
        stmt = stmt.where(QRCode.campaign == campaign)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.scalars(stmt.order_by(QRCode.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [qr_dict(qr) for qr in items], "total": total, "page": page, "page_size": page_size}


@router.post("/qrcodes", response_model=QROut, status_code=201)
def api_create_qr(data: QRCreate, db: Session = Depends(get_db)):
    return qr_dict(create_qr(db, data))


@router.get("/qrcodes/{qr_id}", response_model=QROut)
def api_get_qr(qr_id: int, db: Session = Depends(get_db)):
    return qr_dict(get_qr_or_404(db, qr_id))


@router.put("/qrcodes/{qr_id}", response_model=QROut)
def api_update_qr(qr_id: int, data: QRUpdate, db: Session = Depends(get_db)):
    return qr_dict(update_qr(db, get_qr_or_404(db, qr_id), data))


@router.delete("/qrcodes/{qr_id}", status_code=204)
def api_delete_qr(qr_id: int, db: Session = Depends(get_db)):
    soft_delete_qr(db, get_qr_or_404(db, qr_id))


@router.get("/qrcodes/{qr_id}/stats")
def api_qr_stats(qr_id: int, period: str = Query("30d", pattern="^(today|7d|30d|90d|year)$"), db: Session = Depends(get_db)):
    return qr_stats(db, get_qr_or_404(db, qr_id), period)


@router.get("/dashboard/stats")
def api_dashboard_stats(period: str = Query("30d", pattern="^(today|7d|30d|90d|year)$"), db: Session = Depends(get_db)):
    return dashboard_stats(db, period)


@router.get("/scans")
def api_scans(db: Session = Depends(get_db), qr_id: int | None = None, page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=100)):
    stmt = select(QRScan)
    if qr_id:
        stmt = stmt.where(QRScan.qr_code_id == qr_id)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    scans = db.scalars(stmt.order_by(QRScan.scanned_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [{
        "id": scan.id, "qr_code_id": scan.qr_code_id, "scanned_at": scan.scanned_at,
        "browser": scan.browser, "operating_system": scan.operating_system,
        "device_type": scan.device_type, "referer": scan.referer, "language": scan.language,
        "country": scan.country, "region": scan.region, "city": scan.city,
        "is_unique_scan": scan.is_unique_scan,
    } for scan in scans], "total": total, "page": page, "page_size": page_size}
