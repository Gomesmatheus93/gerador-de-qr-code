import hashlib
import hmac
import ipaddress
from datetime import timedelta
from functools import lru_cache

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import QRCode, QRScan, utcnow


def client_ip(request: Request, settings: Settings) -> str | None:
    if settings.trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        try:
            return str(ipaddress.ip_address(forwarded))
        except ValueError:
            pass
    return request.client.host if request.client else None


def anonymized_ip(ip: str | None) -> str | None:
    if not ip:
        return None
    try:
        address = ipaddress.ip_address(ip)
        prefix = 24 if address.version == 4 else 48
        return str(ipaddress.ip_network(f"{address}/{prefix}", strict=False).network_address)
    except ValueError:
        return None


def classify_user_agent(agent: str) -> tuple[str, str, str]:
    lower = agent.lower()
    if "ipad" in lower or "tablet" in lower:
        device = "Tablet"
    elif any(value in lower for value in ("mobile", "iphone", "android")):
        device = "Mobile"
    else:
        device = "Desktop"
    if "android" in lower:
        system = "Android"
    elif "iphone" in lower or "ipad" in lower or "ios" in lower:
        system = "iOS"
    elif "windows" in lower:
        system = "Windows"
    elif "mac os" in lower or "macintosh" in lower:
        system = "macOS"
    elif "linux" in lower:
        system = "Linux"
    else:
        system = "Outro"
    if "edg/" in lower or "edge/" in lower:
        browser = "Edge"
    elif "firefox/" in lower or "fxios/" in lower:
        browser = "Firefox"
    elif "chrome/" in lower or "crios/" in lower:
        browser = "Chrome"
    elif "safari/" in lower:
        browser = "Safari"
    else:
        browser = "Outro"
    return browser, system, device


@lru_cache(maxsize=2)
def _geo_reader(path: str):
    import geoip2.database

    return geoip2.database.Reader(path)


def approximate_location(ip: str | None, path: str) -> tuple[str | None, str | None, str | None]:
    if not ip or not path:
        return None, None, None
    try:
        result = _geo_reader(path).city(ip)
        return result.country.name, result.subdivisions.most_specific.name, result.city.name
    except Exception:
        return None, None, None


def record_scan(db: Session, qr: QRCode, request: Request, settings: Settings) -> QRScan:
    ip = client_ip(request, settings)
    user_agent = request.headers.get("user-agent", "")[:2048]
    secret = (settings.secret_key or "development-only-key-change-before-production").encode()
    ip_hash = hmac.new(secret, (ip or "").encode(), hashlib.sha256).hexdigest() if ip else None
    session_hash = hmac.new(secret, f"{qr.id}|{ip}|{user_agent}".encode(), hashlib.sha256).hexdigest()
    now = utcnow()
    previous = db.scalar(
        select(QRScan.id).where(
            QRScan.qr_code_id == qr.id,
            QRScan.session_hash == session_hash,
            QRScan.scanned_at >= now - timedelta(seconds=30),
        ).order_by(QRScan.scanned_at.desc()).limit(1)
    )
    browser, operating_system, device_type = classify_user_agent(user_agent)
    country, region, city = approximate_location(ip, settings.geoip_db_path)
    scan = QRScan(
        qr_code_id=qr.id, scanned_at=now,
        ip=anonymized_ip(ip) if settings.anonymize_ip else ip,
        ip_hash=ip_hash, user_agent=user_agent, browser=browser,
        operating_system=operating_system, device_type=device_type,
        referer=request.headers.get("referer", "")[:2048] or None,
        language=request.headers.get("accept-language", "")[:100] or None,
        country=country, region=region, city=city,
        is_unique_scan=previous is None, session_hash=session_hash,
    )
    db.add(scan)
    db.commit()
    return scan
