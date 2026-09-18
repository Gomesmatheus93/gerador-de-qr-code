import secrets
import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import get_settings
from app.models import User
from app.services.tracking import client_ip

password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
http_basic = HTTPBasic()
_rate_buckets: dict[str, deque[float]] = defaultdict(deque)
_rate_lock = Lock()


def hash_password(password: str) -> str:
    if len(password.encode("utf-8")) > 72:
        raise ValueError("A senha deve ter no máximo 72 bytes para bcrypt.")
    return password_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return password_context.verify(password, password_hash)


def rate_allowed(key: str, limit: int, window: int) -> bool:
    now = time.monotonic()
    with _rate_lock:
        bucket = _rate_buckets[key]
        while bucket and bucket[0] <= now - window:
            bucket.popleft()
        if len(bucket) >= limit:
            return False
        bucket.append(now)
        if len(_rate_buckets) > 10000:
            for old_key in list(_rate_buckets)[:1000]:
                if not _rate_buckets[old_key] or _rate_buckets[old_key][0] <= now - 600:
                    _rate_buckets.pop(old_key, None)
        return True


def csrf_token(request: Request) -> str:
    if "csrf" not in request.session:
        request.session["csrf"] = secrets.token_urlsafe(32)
    return request.session["csrf"]


def check_csrf(request: Request, token: str | None) -> None:
    expected = request.session.get("csrf", "")
    if not token or not expected or not secrets.compare_digest(token, expected):
        raise HTTPException(403, "Formulário expirado. Atualize a página e tente novamente.")


def web_user(request: Request, db: Session = Depends(get_db)) -> User:
    user_id = request.session.get("user_id")
    user = db.get(User, user_id) if isinstance(user_id, int) else None
    if user is None:
        raise HTTPException(303, headers={"Location": "/login"})
    return user


def api_user(request: Request, credentials: HTTPBasicCredentials = Depends(http_basic), db: Session = Depends(get_db)) -> User:
    if not rate_allowed(f"api:{client_ip(request, get_settings()) or 'unknown'}", 120, 300):
        raise HTTPException(429, "Muitas solicitações. Aguarde alguns minutos.")
    email = credentials.username.lower().strip()
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(401, "Credenciais inválidas.", headers={"WWW-Authenticate": "Basic"})
    return user
