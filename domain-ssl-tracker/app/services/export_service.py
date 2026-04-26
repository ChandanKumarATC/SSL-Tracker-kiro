import csv
import io
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.domain import Domain


def _days_until(expiry_date: datetime | None) -> str:
    if expiry_date is None:
        return "N/A"
    delta = expiry_date - datetime.utcnow()
    return str(delta.days)


def export_domains_csv(db: Session) -> str:
    """
    Export all domains to a CSV string.
    Returns the CSV content as a string.
    """
    domains = db.query(Domain).order_by(Domain.domain_name).all()

    output = io.StringIO()
    writer = csv.writer(output)

    # Header row
    writer.writerow([
        "ID", "Domain", "SSL Expiry", "SSL Type", "SSL Issuer", "SSL Days Left",
        "Domain Expiry", "Domain Days Left", "Last Checked",
        "Alert Sent (SSL)", "Alert Sent (Domain)", "Created At"
    ])

    for d in domains:
        writer.writerow([
            d.id,
            d.domain_name,
            d.ssl_expiry_date.strftime("%Y-%m-%d") if d.ssl_expiry_date else "",
            d.ssl_type or "",
            d.ssl_issuer or "",
            _days_until(d.ssl_expiry_date),
            d.domain_expiry_date.strftime("%Y-%m-%d") if d.domain_expiry_date else "",
            _days_until(d.domain_expiry_date),
            d.last_checked.strftime("%Y-%m-%d %H:%M") if d.last_checked else "",
            "Yes" if d.alert_sent_ssl else "No",
            "Yes" if d.alert_sent_domain else "No",
            d.created_at.strftime("%Y-%m-%d %H:%M") if d.created_at else "",
        ])

    return output.getvalue()
