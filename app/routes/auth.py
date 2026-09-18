from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.services.security import check_csrf, rate_allowed, verify_password
from app.services.tracking import client_ip
from app.config import get_settings
from app.utils.templates import render

router = APIRouter()


@router.get("/login", include_in_schema=False)
def login_page(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse("/dashboard", status_code=303)
    return render(request, "login.html", {})


@router.post("/login", include_in_schema=False)
def login(request: Request, email: str = Form(...), password: str = Form(...), csrf: str = Form(...), db: Session = Depends(get_db)):
    check_csrf(request, csrf)
    key = f"login:{client_ip(request, get_settings()) or 'unknown'}"
    if not rate_allowed(key, 10, 300):
        return render(request, "login.html", {"error": "Muitas tentativas. Aguarde alguns minutos."}, 429)
    user = db.scalar(select(User).where(User.email == email.lower().strip()))
    if not user or not verify_password(password, user.password_hash):
        return render(request, "login.html", {"error": "E-mail ou senha inválidos."}, 401)
    request.session.clear()
    request.session["user_id"] = user.id
    return RedirectResponse("/dashboard", status_code=303)


@router.post("/logout", include_in_schema=False)
def logout(request: Request, csrf: str = Form(...)):
    check_csrf(request, csrf)
    request.session.clear()
    return RedirectResponse("/login", status_code=303)
