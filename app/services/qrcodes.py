import re
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import QRCode


def clean_slug(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_value.lower()).strip("-")[:200].strip("-")
    if not slug:
        raise ValueError("Informe um nome ou slug com letras ou números.")
    return slug


def validate_destination(value: str) -> str:
    value = value.strip()
    if len(value) > 2048 or any(ord(char) < 33 for char in value) or "\\" in value:
        raise ValueError("URL de destino inválida.")
    try:
        parts = urlsplit(value)
        host = parts.hostname
        port = parts.port
    except ValueError as exc:
        raise ValueError("URL de destino inválida.") from exc
    if parts.scheme not in ("http", "https") or not host or parts.username or parts.password or port == 0:
        raise ValueError("Use uma URL completa iniciada por http:// ou https://, sem credenciais.")
    return value


def next_slug(db: Session, base: str) -> str:
    slug = clean_slug(base)
    candidate = slug
    number = 2
    while db.scalar(select(QRCode.id).where(QRCode.slug == candidate)) is not None:
        candidate = f"{slug[:190]}-{number}"
        number += 1
    return candidate


def get_qr_or_404(db: Session, qr_id: int) -> QRCode:
    qr = db.get(QRCode, qr_id)
    if qr is None or qr.deleted_at is not None:
        raise HTTPException(404, "QR Code não encontrado.")
    return qr


def destination_with_utm(qr: QRCode) -> str:
    destination = validate_destination(qr.destination_url)
    if not qr.utm_enabled:
        return destination
    parts = urlsplit(destination)
    query = parse_qsl(parts.query, keep_blank_values=True)
    additions = []
    for field in ("source", "medium", "campaign", "content", "term"):
        value = getattr(qr, f"utm_{field}")
        if value:
            additions.append((f"utm_{field}", value))
    replaced = {key for key, _ in additions}
    query = [(key, value) for key, value in query if key not in replaced] + additions
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def short_url(slug: str, base_url: str) -> str:
    return f"{base_url.rstrip('/')}/q/{slug}"
