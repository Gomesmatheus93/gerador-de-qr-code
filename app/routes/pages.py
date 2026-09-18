import csv
from datetime import date, timedelta
from io import BytesIO, StringIO

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse, Response
from openpyxl import Workbook
from pydantic import ValidationError
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import QRCode, QRScan, User, utcnow
from app.schemas import QRCreate, QRUpdate
from app.services.crud import create_qr, soft_delete_qr, update_qr
from app.services.images import qr_image
from app.services.qrcodes import get_qr_or_404, short_url
from app.services.security import check_csrf, csrf_token, web_user
from app.services.stats import dashboard_stats, qr_stats, report_data
from app.utils.templates import render

router = APIRouter(dependencies=[Depends(web_user)])


def _form_data(form) -> dict:
    fields = ("name", "destination_url", "campaign", "source", "description", "slug",
              "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term")
    values = {field: str(form.get(field, "")).strip() or None for field in fields}
    values["name"] = values["name"] or ""
    values["destination_url"] = values["destination_url"] or ""
    values["active"] = form.get("active") == "on"
    values["utm_enabled"] = form.get("utm_enabled") == "on"
    return values


def _validation_message(exc: ValidationError) -> str:
    return "; ".join(f"{'.'.join(str(v) for v in error['loc'])}: {error['msg']}" for error in exc.errors())


@router.get("/dashboard", include_in_schema=False)
def dashboard(request: Request, period: str = "30d", db: Session = Depends(get_db), user: User = Depends(web_user)):
    if period not in ("today", "7d", "30d", "90d", "year"):
        period = "30d"
    stats = dashboard_stats(db, period)
    return render(request, "dashboard.html", {"user": user, "stats": stats, "period": period, "page": "dashboard"})


@router.get("/qrcodes", include_in_schema=False)
def qr_list(request: Request, search: str = "", status: str = "all", campaign: str = "", created: str = "", page: int = Query(1, ge=1), db: Session = Depends(get_db), user: User = Depends(web_user)):
    stmt = select(QRCode).where(QRCode.deleted_at.is_(None))
    if search.strip():
        pattern = f"%{search.strip()}%"
        stmt = stmt.where(or_(QRCode.name.ilike(pattern), QRCode.slug.ilike(pattern), QRCode.campaign.ilike(pattern), QRCode.destination_url.ilike(pattern)))
    if status in ("active", "inactive"):
        stmt = stmt.where(QRCode.active.is_(status == "active"))
    if campaign:
        stmt = stmt.where(QRCode.campaign == campaign)
    if created:
        try:
            chosen = date.fromisoformat(created)
            stmt = stmt.where(func.date(QRCode.created_at) == chosen.isoformat())
        except ValueError:
            created = ""
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    page_size = 12
    page = min(page, max(1, (total + page_size - 1) // page_size))
    scans = select(QRScan.qr_code_id, func.count(QRScan.id).label("total"), func.max(QRScan.scanned_at).label("last"))\
        .group_by(QRScan.qr_code_id).subquery()
    rows = db.execute(stmt.outerjoin(scans, scans.c.qr_code_id == QRCode.id)
        .with_only_columns(QRCode, scans.c.total, scans.c.last)
        .order_by(QRCode.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    campaigns = db.scalars(select(QRCode.campaign).where(QRCode.deleted_at.is_(None), QRCode.campaign.is_not(None)).distinct().order_by(QRCode.campaign)).all()
    return render(request, "qrcodes.html", {"user": user, "page": "qrcodes", "rows": rows, "total": total,
        "page_num": page, "pages": max(1, (total + page_size - 1) // page_size),
        "search": search, "status": status, "campaign": campaign, "created": created, "campaigns": campaigns})


@router.get("/qrcodes/create", include_in_schema=False)
def qr_create_page(request: Request, user: User = Depends(web_user)):
    return render(request, "qr_form.html", {"user": user, "page": "create", "qr": None, "values": None})


@router.post("/qrcodes/create", include_in_schema=False)
async def qr_create(request: Request, db: Session = Depends(get_db), user: User = Depends(web_user)):
    form = await request.form()
    check_csrf(request, form.get("csrf"))
    values = _form_data(form)
    try:
        qr = create_qr(db, QRCreate.model_validate(values))
    except (ValidationError, ValueError, HTTPException) as exc:
        message = _validation_message(exc) if isinstance(exc, ValidationError) else str(getattr(exc, "detail", exc))
        return render(request, "qr_form.html", {"user": user, "page": "create", "qr": None, "values": values, "error": message}, 400)
    return RedirectResponse(f"/qrcodes/{qr.id}", status_code=303)


@router.get("/qrcodes/{qr_id}", include_in_schema=False)
def qr_detail(qr_id: int, request: Request, period: str = "30d", db: Session = Depends(get_db), user: User = Depends(web_user)):
    qr = get_qr_or_404(db, qr_id)
    if period not in ("today", "7d", "30d", "90d", "year"):
        period = "30d"
    stats = qr_stats(db, qr, period)
    recent = db.scalars(select(QRScan).where(QRScan.qr_code_id == qr.id).order_by(QRScan.scanned_at.desc()).limit(20)).all()
    return render(request, "qr_detail.html", {"user": user, "page": "qrcodes", "qr": qr, "stats": stats,
        "recent": recent, "period": period, "short_url": short_url(qr.slug, get_settings().base_url)})


@router.get("/qrcodes/{qr_id}/edit", include_in_schema=False)
def qr_edit_page(qr_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(web_user)):
    qr = get_qr_or_404(db, qr_id)
    return render(request, "qr_form.html", {"user": user, "page": "qrcodes", "qr": qr, "values": qr})


@router.post("/qrcodes/{qr_id}/edit", include_in_schema=False)
async def qr_edit(qr_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(web_user)):
    qr = get_qr_or_404(db, qr_id)
    form = await request.form()
    check_csrf(request, form.get("csrf"))
    values = _form_data(form)
    values["confirm_slug_change"] = form.get("confirm_slug_change") == "on"
    try:
        update_qr(db, qr, QRUpdate.model_validate(values))
    except (ValidationError, ValueError, HTTPException) as exc:
        message = _validation_message(exc) if isinstance(exc, ValidationError) else str(getattr(exc, "detail", exc))
        return render(request, "qr_form.html", {"user": user, "page": "qrcodes", "qr": qr, "values": values, "error": message}, 400)
    return RedirectResponse(f"/qrcodes/{qr_id}", status_code=303)


@router.post("/qrcodes/{qr_id}/duplicate", include_in_schema=False)
async def qr_duplicate(qr_id: int, request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    check_csrf(request, form.get("csrf"))
    qr = get_qr_or_404(db, qr_id)
    values = {field: getattr(qr, field) for field in QRCreate.model_fields if field != "slug"}
    values["name"] = f"{qr.name} (cópia)"[:180]
    values["slug"] = qr.slug
    new_qr = create_qr(db, QRCreate.model_validate(values))
    return RedirectResponse(f"/qrcodes/{new_qr.id}", status_code=303)


@router.post("/qrcodes/{qr_id}/toggle", include_in_schema=False)
async def qr_toggle(qr_id: int, request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    check_csrf(request, form.get("csrf"))
    qr = get_qr_or_404(db, qr_id)
    qr.active = not qr.active
    db.commit()
    return RedirectResponse(request.headers.get("referer", "/qrcodes") if request.headers.get("referer", "").startswith(str(request.base_url)) else "/qrcodes", status_code=303)


@router.post("/qrcodes/{qr_id}/delete", include_in_schema=False)
async def qr_delete(qr_id: int, request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    check_csrf(request, form.get("csrf"))
    soft_delete_qr(db, get_qr_or_404(db, qr_id))
    return RedirectResponse("/qrcodes", status_code=303)


@router.get("/qrcodes/{qr_id}/image", include_in_schema=False)
def qr_download(qr_id: int, fmt: str = Query("png", pattern="^(png|svg|pdf)$"), size: int = Query(500), download: bool = False, db: Session = Depends(get_db)):
    qr = get_qr_or_404(db, qr_id)
    try:
        content, media_type = qr_image(short_url(qr.slug, get_settings().base_url), fmt, size)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    headers = {"Cache-Control": "private, no-store"}
    if download:
        headers["Content-Disposition"] = f'attachment; filename="{qr.slug}-{size}.{fmt}"'
    return Response(content, media_type=media_type, headers=headers)


def _report_dates(start: str | None, end: str | None, period: str) -> tuple[date, date]:
    today = utcnow().date()
    if start or end:
        try:
            first, last = date.fromisoformat(start or ""), date.fromisoformat(end or "")
        except ValueError as exc:
            raise HTTPException(400, "Datas inválidas.") from exc
    else:
        days = {"today": 1, "7d": 7, "30d": 30, "90d": 90, "year": 365}.get(period, 30)
        first, last = today - timedelta(days=days - 1), today
        if period == "year":
            first = date(today.year, 1, 1)
    if first > last or (last - first).days > 3660:
        raise HTTPException(400, "Escolha um período válido de até 10 anos.")
    return first, last


@router.get("/reports", include_in_schema=False)
def reports(request: Request, qr_id: int | None = None, campaign: str = "", period: str = "30d", start: str | None = None, end: str | None = None, export: str | None = None, db: Session = Depends(get_db), user: User = Depends(web_user)):
    if qr_id:
        if db.get(QRCode, qr_id) is None:
            raise HTTPException(404, "QR Code não encontrado.")
    first, last = _report_dates(start, end, period)
    result = report_data(db, qr_id, campaign or None, first, last)
    if export in ("csv", "xlsx"):
        headings = ["Data UTC", "QR ID", "Único", "Dispositivo", "Sistema", "Navegador", "País", "Região", "Cidade", "Origem"]
        rows = [[scan.scanned_at.isoformat(sep=" "), scan.qr_code_id, "Sim" if scan.is_unique_scan else "Não",
                 scan.device_type, scan.operating_system, scan.browser, scan.country, scan.region, scan.city, scan.referer]
                for scan in result["scans"]]
        def safe(value):
            if isinstance(value, str) and value.startswith(("=", "+", "-", "@", "\t", "\r")):
                return "'" + value
            return value if value is not None else ""
        if export == "csv":
            output = StringIO()
            writer = csv.writer(output)
            writer.writerow(headings)
            writer.writerows([[safe(value) for value in row] for row in rows])
            return Response("\ufeff" + output.getvalue(), media_type="text/csv; charset=utf-8",
                headers={"Content-Disposition": 'attachment; filename="relatorio-qr.csv"'})
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Scans"
        sheet.append(headings)
        for row in rows:
            sheet.append([safe(value) for value in row])
        stream = BytesIO()
        workbook.save(stream)
        return Response(stream.getvalue(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": 'attachment; filename="relatorio-qr.xlsx"'})
    qrs = db.scalars(select(QRCode).order_by(QRCode.name)).all()
    campaigns = db.scalars(select(QRCode.campaign).where(QRCode.campaign.is_not(None)).distinct().order_by(QRCode.campaign)).all()
    return render(request, "reports.html", {"user": user, "page": "reports", "result": result, "qrs": qrs,
        "campaigns": campaigns, "qr_id": qr_id, "campaign": campaign, "period": period,
        "start": first.isoformat(), "end": last.isoformat()})


@router.get("/settings", include_in_schema=False)
def settings_page(request: Request, user: User = Depends(web_user)):
    settings = get_settings()
    return render(request, "settings.html", {"user": user, "page": "settings", "app_settings": settings})
