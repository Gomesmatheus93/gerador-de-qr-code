import re

from app.models import QRCode, QRScan
from app.models import User
from app.services.security import verify_password
from app.services.tracking import anonymized_ip
from app.services.stats import report_data
from app.models import utcnow
from tests.conftest import login


def test_authentication_and_csrf(client, basic_auth):
    http, _ = client
    assert http.get("/dashboard").status_code == 303
    assert http.get("/api/qrcodes").status_code == 401
    assert http.get("/api/qrcodes", headers=basic_auth).status_code == 200
    assert http.post("/login", data={"email": "admin@example.com", "password": "correct-password", "csrf": "bad"}).status_code == 403
    assert login(http).status_code == 303
    assert http.get("/dashboard").status_code == 200


def test_qr_creation_redirect_scan_and_edit(client, basic_auth):
    http, session_factory = client
    payload = {"name": "Allpfit Capim Macio", "destination_url": "https://connect.alleenergia.com/", "campaign": "Allpfit", "active": True}
    created = http.post("/api/qrcodes", headers=basic_auth, json=payload)
    assert created.status_code == 201, created.text
    qr = created.json()
    assert qr["slug"] == "allpfit-capim-macio"
    assert qr["short_url"].endswith("/q/allpfit-capim-macio")
    duplicate = http.post("/api/qrcodes", headers=basic_auth, json=payload)
    assert duplicate.json()["slug"] == "allpfit-capim-macio-2"
    image = http.get(f"/qrcodes/{qr['id']}/image?fmt=png&size=1000")
    assert image.status_code == 303  # Admin image route is protected.
    assert login(http).status_code == 303
    image = http.get(f"/qrcodes/{qr['id']}/image?fmt=png&size=1000")
    assert image.status_code == 200 and image.content.startswith(b"\x89PNG")
    assert http.get(f"/qrcodes/{qr['id']}/image?fmt=svg").status_code == 200
    assert http.get(f"/qrcodes/{qr['id']}/image?fmt=pdf").content.startswith(b"%PDF")
    assert http.get("/qrcodes").status_code == 200
    assert http.get(f"/qrcodes/{qr['id']}").status_code == 200
    assert http.get(f"/qrcodes/{qr['id']}/edit").status_code == 200
    first = http.get(f"/q/{qr['slug']}", headers={"User-Agent": "Mozilla/5.0 Chrome/120.0 Windows"})
    second = http.get(f"/q/{qr['slug']}", headers={"User-Agent": "Mozilla/5.0 Chrome/120.0 Windows"})
    assert first.status_code == 302 and first.headers["location"] == payload["destination_url"]
    assert second.status_code == 302
    with session_factory() as db:
        scans = db.query(QRScan).filter_by(qr_code_id=qr["id"]).all()
        assert len(scans) == 2
        assert [scan.is_unique_scan for scan in scans] == [True, False]
        assert scans[0].session_hash and scans[0].ip_hash
    changed = http.put(f"/api/qrcodes/{qr['id']}", headers=basic_auth, json={**payload, "destination_url": "https://new.example.com/path?existing=1", "utm_enabled": True, "utm_source": "qrcode"})
    assert changed.status_code == 200, changed.text
    assert changed.json()["slug"] == qr["slug"]
    redirected = http.get(f"/q/{qr['slug']}")
    assert redirected.headers["location"] == "https://new.example.com/path?existing=1&utm_source=qrcode"
    stats = http.get(f"/api/qrcodes/{qr['id']}/stats", headers=basic_auth).json()
    assert stats["total_scans"] == 3 and stats["unique_scans"] == 2
    assert http.get("/dashboard").status_code == 200
    assert http.get("/reports").status_code == 200
    assert http.get("/reports?export=csv").content.startswith(b"\xef\xbb\xbf")
    assert http.get("/reports?export=xlsx").content.startswith(b"PK")


def test_missing_inactive_soft_delete_and_slug_confirmation(client, basic_auth):
    http, session_factory = client
    assert http.get("/q/not-found").status_code == 404
    payload = {"name": "Recepção", "destination_url": "https://example.com/", "active": False}
    qr = http.post("/api/qrcodes", headers=basic_auth, json=payload).json()
    assert http.get(f"/q/{qr['slug']}").status_code == 410
    with session_factory() as db:
        assert db.query(QRScan).count() == 0
    failed = http.put(f"/api/qrcodes/{qr['id']}", headers=basic_auth, json={**payload, "slug": "new-slug"})
    assert failed.status_code == 400
    accepted = http.put(f"/api/qrcodes/{qr['id']}", headers=basic_auth, json={**payload, "slug": "new-slug", "confirm_slug_change": True, "active": True})
    assert accepted.status_code == 200
    assert http.get("/q/new-slug").status_code == 302
    assert http.delete(f"/api/qrcodes/{qr['id']}", headers=basic_auth).status_code == 204
    assert http.get("/q/new-slug").status_code == 404
    with session_factory() as db:
        assert db.get(QRCode, qr["id"]).deleted_at is not None
        assert report_data(db, qr["id"], None, utcnow().date(), utcnow().date())["total_scans"] == 1
    assert login(http).status_code == 303
    assert http.get(f"/reports?qr_id={qr['id']}").status_code == 200


def test_invalid_urls_and_dashboard_stats(client, basic_auth):
    http, _ = client
    for dangerous in ("javascript:alert(1)", "file:///etc/passwd", "data:text/html,hi", "https://user:pass@example.com"):
        assert http.post("/api/qrcodes", headers=basic_auth, json={"name": "Bad", "destination_url": dangerous}).status_code == 422
    assert http.post("/api/qrcodes", headers=basic_auth, json={"name": "!!!", "destination_url": "https://example.com"}).status_code == 422
    result = http.get("/api/dashboard/stats?period=7d", headers=basic_auth)
    assert result.status_code == 200
    assert result.json()["total_qrcodes"] == 0
    assert anonymized_ip("192.0.2.123") == "192.0.2.0"


def test_web_form_creation(client):
    http, _ = client
    assert login(http).status_code == 303
    form_page = http.get("/qrcodes/create")
    assert form_page.status_code == 200
    token = re.search(r'name="csrf" value="([^"]+)"', form_page.text).group(1)
    created = http.post("/qrcodes/create", data={
        "csrf": token, "name": "Unidade Centro", "destination_url": "https://example.org/",
        "active": "on", "utm_enabled": "on", "utm_source": "qrcode",
    })
    assert created.status_code == 303
    assert http.get(created.headers["location"]).status_code == 200
    assert http.get("/q/unidade-centro").headers["location"] == "https://example.org/?utm_source=qrcode"


def test_static_assets_use_https_safe_paths(client):
    http, _ = client
    login_page = http.get("/login", headers={"host": "example.com", "x-forwarded-proto": "https"})
    assert 'href="/static/styles.css"' in login_page.text
    assert login(http).status_code == 303
    dashboard = http.get("/dashboard", headers={"host": "example.com", "x-forwarded-proto": "https"})
    assert 'href="/static/styles.css"' in dashboard.text
    assert 'src="/static/app.js"' in dashboard.text
    assert http.get("/static/styles.css").status_code == 200


def test_admin_password_can_be_rotated(client, monkeypatch):
    _, session_factory = client
    import app.cli as cli

    monkeypatch.setattr(cli, "SessionLocal", session_factory)
    monkeypatch.setenv("ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setenv("ADMIN_PASSWORD", "a-new-strong-password")
    cli.reset_admin_password()
    with session_factory() as db:
        user = db.query(User).filter_by(email="admin@example.com").one()
        assert verify_password("a-new-strong-password", user.password_hash)
        assert not verify_password("correct-password", user.password_hash)
