from fastapi import APIRouter, Depends, Request, Form, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime
import io

from app.database import get_db
from app.models.domain import Domain
from app.services.checker import run_all_checks, check_and_update_domain
from app.services.export_service import export_domains_csv
from app.auth import is_logged_in, require_login

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _days_until(expiry_date: datetime | None) -> int | None:
    if expiry_date is None:
        return None
    return (expiry_date - datetime.utcnow()).days


def _status_label(days: int | None) -> str:
    if days is None:
        return "unknown"
    if days < 0:
        return "expired"
    if days <= 14:
        return "critical"
    if days <= 30:
        return "warning"
    return "safe"


def _enrich(domain: Domain) -> dict:
    ssl_days = _days_until(domain.ssl_expiry_date)
    domain_days = _days_until(domain.domain_expiry_date)

    # Overall urgency: use the smallest non-None days value
    candidates = [d for d in [ssl_days, domain_days] if d is not None]
    min_days = min(candidates) if candidates else None

    return {
        "id": domain.id,
        "domain_name": domain.domain_name,
        "ssl_expiry_date": domain.ssl_expiry_date,
        "ssl_type": domain.ssl_type,
        "ssl_issuer": domain.ssl_issuer,
        "ssl_error": domain.ssl_error,
        "domain_expiry_date": domain.domain_expiry_date,
        "last_checked": domain.last_checked,
        "ssl_days": ssl_days,
        "domain_days": domain_days,
        "ssl_status": _status_label(ssl_days),
        "domain_status": _status_label(domain_days),
        "min_days": min_days if min_days is not None else 9999,
    }


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    """Main dashboard — sorted by SSL expiry days ascending (nearest first)."""
    domains = db.query(Domain).all()
    enriched = [_enrich(d) for d in domains]
    enriched.sort(key=lambda x: (
        x["ssl_days"] if x["ssl_days"] is not None else 99999,
        x["domain_days"] if x["domain_days"] is not None else 99999,
    ))
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "domains": enriched,
        "now": datetime.utcnow(),
        "logged_in": is_logged_in(request),
    })


@router.post("/add-domain", response_class=RedirectResponse)
def add_domain_form(
    request: Request,
    domain_name: str = Form(...),
    db: Session = Depends(get_db),
    _: None = Depends(require_login),
):
    """Handle add-domain form submission."""
    domain_name = domain_name.strip().lower()
    domain_name = domain_name.replace("https://", "").replace("http://", "").split("/")[0]

    existing = db.query(Domain).filter(Domain.domain_name == domain_name).first()
    if not existing:
        new_domain = Domain(domain_name=domain_name)
        db.add(new_domain)
        db.commit()

    return RedirectResponse(url="/", status_code=303)


@router.post("/delete-domain/{domain_id}", response_class=RedirectResponse)
def delete_domain_form(domain_id: int, db: Session = Depends(get_db), _: None = Depends(require_login)):
    """Handle delete button from dashboard."""
    domain = db.query(Domain).filter(Domain.id == domain_id).first()
    if domain:
        db.delete(domain)
        db.commit()
    return RedirectResponse(url="/", status_code=303)


@router.post("/check-domain/{domain_id}", response_class=RedirectResponse)
def check_domain_form(domain_id: int, db: Session = Depends(get_db), _: None = Depends(require_login)):
    """Trigger a check for a single domain from the dashboard."""
    domain = db.query(Domain).filter(Domain.id == domain_id).first()
    if domain:
        check_and_update_domain(db, domain)
    return RedirectResponse(url="/", status_code=303)


@router.post("/check-all", response_class=RedirectResponse)
def check_all_form(db: Session = Depends(get_db), _: None = Depends(require_login)):
    """Trigger checks for all domains from the dashboard."""
    run_all_checks(db)
    return RedirectResponse(url="/", status_code=303)


@router.post("/edit-domain/{domain_id}", response_class=RedirectResponse)
def edit_domain_form(
    domain_id: int,
    domain_name: str = Form(...),
    db: Session = Depends(get_db),
    _: None = Depends(require_login),
):
    """Handle inline edit of domain name from dashboard."""
    domain = db.query(Domain).filter(Domain.id == domain_id).first()
    if domain:
        new_name = domain_name.strip().lower()
        new_name = new_name.replace("https://", "").replace("http://", "").split("/")[0]
        if new_name and "." in new_name:
            conflict = db.query(Domain).filter(
                Domain.domain_name == new_name, Domain.id != domain_id
            ).first()
            if not conflict:
                domain.domain_name = new_name
                # Reset all check data so it gets re-checked fresh
                domain.ssl_expiry_date = None
                domain.ssl_type = None
                domain.ssl_issuer = None
                domain.ssl_error = None
                domain.domain_expiry_date = None
                domain.last_checked = None
                domain.alert_sent_ssl = False
                domain.alert_sent_domain = False
                db.commit()
    return RedirectResponse(url="/", status_code=303)


@router.post("/bulk-import", response_class=RedirectResponse)
async def bulk_import(
    file: UploadFile = File(None),
    domains_text: str = Form(""),
    db: Session = Depends(get_db),
    _: None = Depends(require_login),
):
    """
    Bulk import domains from either:
      - A plain text / CSV file upload (one domain per line, or CSV with domain in first column)
      - A textarea with one domain per line
    Skips duplicates and invalid entries silently.
    """
    raw_lines = []

    # ── From uploaded file ────────────────────────────────────────────────
    if file and file.filename:
        content = await file.read()
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            text = content.decode("latin-1")
        raw_lines.extend(text.splitlines())

    # ── From textarea ─────────────────────────────────────────────────────
    if domains_text.strip():
        raw_lines.extend(domains_text.splitlines())

    added = 0
    for line in raw_lines:
        # Strip whitespace and comments
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        # CSV: take first column only
        domain_name = line.split(",")[0].strip().strip('"').strip("'")

        # Normalise
        domain_name = domain_name.lower()
        domain_name = domain_name.replace("https://", "").replace("http://", "").split("/")[0]

        # Basic validation
        if not domain_name or "." not in domain_name or " " in domain_name:
            continue

        # Skip duplicates
        existing = db.query(Domain).filter(Domain.domain_name == domain_name).first()
        if not existing:
            db.add(Domain(domain_name=domain_name))
            added += 1

    if added:
        db.commit()

    return RedirectResponse(url="/", status_code=303)


@router.get("/export-csv")
def export_csv(db: Session = Depends(get_db)):
    """Download all domains as a CSV file."""
    csv_content = export_domains_csv(db)
    filename = f"domains_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        io.StringIO(csv_content),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
