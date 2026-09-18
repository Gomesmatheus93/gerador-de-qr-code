from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from pathlib import Path

from app.config import get_settings
from app.routes import api, auth, pages, redirects
from app.utils.templates import render

settings = get_settings()
app = FastAPI(title="QR Atlas", version="1.0.0", docs_url="/docs")
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key or "development-only-key-change-before-production",
    session_cookie="qr_atlas_session", max_age=60 * 60 * 8,
    same_site="lax", https_only=settings.production,
)
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
app.include_router(auth.router)
app.include_router(pages.router)
app.include_router(api.router)
app.include_router(redirects.router)


@app.get("/", include_in_schema=False)
def home(request: Request):
    return RedirectResponse("/dashboard" if request.session.get("user_id") else "/login", status_code=303)


@app.get("/health", include_in_schema=False)
def health():
    return {"status": "ok"}


@app.exception_handler(404)
async def not_found(request: Request, exc):
    if request.url.path.startswith("/api/"):
        return JSONResponse({"detail": "Não encontrado"}, status_code=404)
    return render(request, "error.html", {"title": "Página não encontrada", "message": "O endereço solicitado não existe."}, 404)
