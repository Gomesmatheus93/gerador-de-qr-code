from pathlib import Path

from fastapi import Request
from fastapi.templating import Jinja2Templates

from app.config import get_settings
from app.services.security import csrf_token

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))


def render(request: Request, name: str, context: dict | None = None, status_code: int = 200):
    response = templates.TemplateResponse(
        request=request, name=name,
        context={"csrf_token": csrf_token(request), "settings": get_settings(), **(context or {})},
        status_code=status_code,
    )
    response.headers["Cache-Control"] = "no-store"
    return response
