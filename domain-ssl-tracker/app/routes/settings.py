from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.settings_service import get_all, save_all
from app.services.email_service import send_test_email

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request, db: Session = Depends(get_db), saved: str = "", error: str = ""):
    """Mail settings page."""
    current = get_all(db)
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "s": current,
        "saved": saved,
        "error": error,
    })


@router.post("/settings", response_class=RedirectResponse)
def save_settings(
    request: Request,
    smtp_host: str = Form(""),
    smtp_port: str = Form("587"),
    smtp_user: str = Form(""),
    smtp_password: str = Form(""),
    alert_from_email: str = Form(""),
    alert_to_email: str = Form(""),
    ssl_alert_days: str = Form("7"),
    domain_alert_days: str = Form("30"),
    db: Session = Depends(get_db),
):
    """Save mail settings to DB."""
    save_all(db, {
        "smtp_host":         smtp_host.strip(),
        "smtp_port":         smtp_port.strip() or "587",
        "smtp_user":         smtp_user.strip(),
        "smtp_password":     smtp_password.strip(),
        "alert_from_email":  alert_from_email.strip(),
        "alert_to_email":    alert_to_email.strip(),
        "ssl_alert_days":    ssl_alert_days.strip() or "7",
        "domain_alert_days": domain_alert_days.strip() or "30",
    })
    return RedirectResponse(url="/settings?saved=1", status_code=303)


@router.post("/settings/test-email", response_class=RedirectResponse)
def test_email(db: Session = Depends(get_db)):
    """Send a test email using current saved settings."""
    success, msg = send_test_email(db=db)
    if success:
        return RedirectResponse(url="/settings?saved=test", status_code=303)
    return RedirectResponse(url=f"/settings?error={msg}", status_code=303)


@router.get("/guide/wildcard-ssl", response_class=HTMLResponse)
def wildcard_guide(request: Request):
    """Wildcard SSL certificate guide page."""
    return templates.TemplateResponse("wildcard_guide.html", {"request": request})


@router.get("/tools/wildcard-generator", response_class=HTMLResponse)
def wildcard_generator(request: Request):
    """Interactive wildcard SSL command generator tool."""
    return templates.TemplateResponse("wildcard_generator.html", {"request": request})
