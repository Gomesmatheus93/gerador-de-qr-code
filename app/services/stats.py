from collections import Counter
from datetime import date, datetime, time, timedelta

from sqlalchemy import Integer, func, select
from sqlalchemy.orm import Session

from app.models import QRCode, QRScan, utcnow


def bounds(period: str) -> tuple[datetime, datetime]:
    today = utcnow().date()
    tomorrow = datetime.combine(today + timedelta(days=1), time.min)
    if period == "today":
        start = today
    elif period == "year":
        start = date(today.year, 1, 1)
    else:
        days = {"7d": 7, "30d": 30, "90d": 90}.get(period, 30)
        start = today - timedelta(days=days - 1)
    return datetime.combine(start, time.min), tomorrow


def scan_counts(db: Session, qr_id: int | None = None) -> dict:
    now = utcnow()
    stmt = select(
        func.count(QRScan.id),
        func.coalesce(func.sum(QRScan.is_unique_scan.cast(Integer)), 0),
        func.max(QRScan.scanned_at),
    )
    if qr_id is not None:
        stmt = stmt.where(QRScan.qr_code_id == qr_id)
    total, unique, last_scan = db.execute(stmt).one()
    result = {"total_scans": total, "unique_scans": int(unique), "last_scan": last_scan}
    for key, days in (("today", 1), ("7d", 7), ("30d", 30)):
        start = datetime.combine(now.date() - timedelta(days=days - 1), time.min)
        q = select(func.count(QRScan.id)).where(QRScan.scanned_at >= start)
        if qr_id is not None:
            q = q.where(QRScan.qr_code_id == qr_id)
        result[f"scans_{key}"] = db.scalar(q) or 0
    return result


def daily_scans(db: Session, period: str = "30d", qr_id: int | None = None, *, start: datetime | None = None, end: datetime | None = None) -> dict:
    if start is None or end is None:
        start, end = bounds(period)
    stmt = select(func.date(QRScan.scanned_at), func.count(QRScan.id)).where(
        QRScan.scanned_at >= start, QRScan.scanned_at < end
    )
    if qr_id is not None:
        stmt = stmt.where(QRScan.qr_code_id == qr_id)
    values = {str(day): count for day, count in db.execute(stmt.group_by(func.date(QRScan.scanned_at))).all()}
    labels, counts = [], []
    day = start.date()
    while day < end.date():
        labels.append(day.isoformat())
        counts.append(values.get(day.isoformat(), 0))
        day += timedelta(days=1)
    return {"labels": labels, "values": counts}


def distribution(db: Session, field, start: datetime | None = None, end: datetime | None = None, qr_id: int | None = None, campaign: str | None = None, limit: int = 10) -> list[dict]:
    stmt = select(field, func.count(QRScan.id)).join(QRCode, QRCode.id == QRScan.qr_code_id).where(QRCode.deleted_at.is_(None))
    if start:
        stmt = stmt.where(QRScan.scanned_at >= start)
    if end:
        stmt = stmt.where(QRScan.scanned_at < end)
    if qr_id:
        stmt = stmt.where(QRScan.qr_code_id == qr_id)
    if campaign:
        stmt = stmt.where(QRCode.campaign == campaign)
    rows = db.execute(stmt.group_by(field).order_by(func.count(QRScan.id).desc()).limit(limit)).all()
    return [{"name": name or "Não identificado", "count": count} for name, count in rows]


def dashboard_stats(db: Session, period: str = "30d") -> dict:
    start, end = bounds(period)
    counts = scan_counts(db)
    qr_counts = db.execute(select(QRCode.active, func.count(QRCode.id)).where(QRCode.deleted_at.is_(None)).group_by(QRCode.active)).all()
    active_count = next((count for active, count in qr_counts if active), 0)
    inactive_count = next((count for active, count in qr_counts if not active), 0)
    top_qr = db.execute(select(QRCode.id, QRCode.name, func.count(QRScan.id).label("count"))
        .join(QRScan, QRScan.qr_code_id == QRCode.id)
        .where(QRCode.deleted_at.is_(None))
        .group_by(QRCode.id, QRCode.name)
        .order_by(func.count(QRScan.id).desc()).limit(1)).first()
    per_qr = db.execute(select(QRCode.name, func.count(QRScan.id))
        .join(QRScan, QRScan.qr_code_id == QRCode.id)
        .where(QRCode.deleted_at.is_(None), QRScan.scanned_at >= start, QRScan.scanned_at < end)
        .group_by(QRCode.id, QRCode.name).order_by(func.count(QRScan.id).desc()).limit(8)).all()
    return {
        **counts, "total_qrcodes": active_count + inactive_count,
        "active_qrcodes": active_count, "inactive_qrcodes": inactive_count,
        "top_qr": {"id": top_qr.id, "name": top_qr.name, "scans": top_qr.count} if top_qr else None,
        "daily": daily_scans(db, period),
        "per_qr": [{"name": name, "count": count} for name, count in per_qr],
        "devices": distribution(db, QRScan.device_type, start, end),
        "operating_systems": distribution(db, QRScan.operating_system, start, end),
        "browsers": distribution(db, QRScan.browser, start, end),
        "period": period,
    }


def qr_stats(db: Session, qr: QRCode, period: str = "30d") -> dict:
    start, end = bounds(period)
    return {
        **scan_counts(db, qr.id),
        "daily": daily_scans(db, period, qr.id),
        "devices": distribution(db, QRScan.device_type, start, end, qr.id),
        "browsers": distribution(db, QRScan.browser, start, end, qr.id),
        "operating_systems": distribution(db, QRScan.operating_system, start, end, qr.id),
        "period": period,
    }


def report_data(db: Session, qr_id: int | None, campaign: str | None, start_date: date, end_date: date) -> dict:
    start = datetime.combine(start_date, time.min)
    end = datetime.combine(end_date + timedelta(days=1), time.min)
    stmt = select(QRScan).join(QRCode, QRCode.id == QRScan.qr_code_id).where(
        QRScan.scanned_at >= start, QRScan.scanned_at < end
    )
    if qr_id:
        stmt = stmt.where(QRScan.qr_code_id == qr_id)
    if campaign:
        stmt = stmt.where(QRCode.campaign == campaign)
    scans = db.scalars(stmt.order_by(QRScan.scanned_at.desc())).all()
    days = Counter(scan.scanned_at.date().isoformat() for scan in scans)
    best_day, best_count = days.most_common(1)[0] if days else (None, 0)
    return {
        "total_scans": len(scans),
        "unique_scans": sum(scan.is_unique_scan for scan in scans),
        "average_per_day": round(len(scans) / ((end_date - start_date).days + 1), 2),
        "best_day": best_day, "best_day_scans": best_count,
        "daily": daily_scans(db, start=start, end=end, qr_id=qr_id) if not campaign else _daily_for_scans(scans, start_date, end_date),
        "devices": _count_field(scans, "device_type"),
        "browsers": _count_field(scans, "browser"),
        "operating_systems": _count_field(scans, "operating_system"),
        "cities": _count_field(scans, "city"),
        "countries": _count_field(scans, "country"),
        "scans": scans,
    }


def _count_field(scans: list[QRScan], field: str) -> list[dict]:
    counts = Counter(getattr(scan, field) or "Não identificado" for scan in scans)
    return [{"name": key, "count": value} for key, value in counts.most_common(10)]


def _daily_for_scans(scans: list[QRScan], start: date, end: date) -> dict:
    values = Counter(scan.scanned_at.date().isoformat() for scan in scans)
    labels = [(start + timedelta(days=day)).isoformat() for day in range((end - start).days + 1)]
    return {"labels": labels, "values": [values[label] for label in labels]}
