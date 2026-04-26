import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.domain import Domain
from app.services.ssl_checker import check_ssl
from app.services.whois_checker import check_whois
from app.services.email_service import send_ssl_alert, send_domain_alert
from app.config import SSL_ALERT_DAYS, DOMAIN_ALERT_DAYS

logger = logging.getLogger(__name__)


def _days_until(expiry_date: datetime | None) -> int | None:
    """Return number of days until expiry_date, or None if unknown."""
    if expiry_date is None:
        return None
    now = datetime.utcnow()
    delta = expiry_date - now
    return delta.days


def check_and_update_domain(db: Session, domain: Domain) -> dict:
    """
    Run SSL + WHOIS checks for a single domain, update DB, send alerts.
    Returns a summary dict.
    """
    summary = {"domain": domain.domain_name, "ssl_error": None, "whois_error": None}

    # --- SSL Check ---
    ssl_result = check_ssl(domain.domain_name)
    summary["ssl_error"] = ssl_result.get("error")

    old_ssl_expiry = domain.ssl_expiry_date
    if ssl_result["expiry_date"]:
        domain.ssl_expiry_date = ssl_result["expiry_date"]
        domain.ssl_type = ssl_result["ssl_type"]
        domain.ssl_issuer = ssl_result.get("issuer")
        domain.ssl_error = None  # clear previous error on success

        # Reset alert flag if domain was renewed (expiry moved forward)
        if old_ssl_expiry and ssl_result["expiry_date"] > old_ssl_expiry:
            domain.alert_sent_ssl = False
    else:
        # Store the error so the dashboard can show it
        domain.ssl_error = ssl_result.get("error")

    # --- WHOIS Check ---
    whois_result = check_whois(domain.domain_name)
    summary["whois_error"] = whois_result.get("error")

    old_domain_expiry = domain.domain_expiry_date
    if whois_result["expiry_date"]:
        domain.domain_expiry_date = whois_result["expiry_date"]

        # Reset alert flag if domain was renewed
        if old_domain_expiry and whois_result["expiry_date"] > old_domain_expiry:
            domain.alert_sent_domain = False

    domain.last_checked = datetime.utcnow()

    # --- SSL Alert ---
    ssl_days = _days_until(domain.ssl_expiry_date)
    if ssl_days is not None and ssl_days <= SSL_ALERT_DAYS and not domain.alert_sent_ssl:
        sent = send_ssl_alert(domain.domain_name, domain.ssl_expiry_date, ssl_days)
        if sent:
            domain.alert_sent_ssl = True
            logger.info("SSL alert sent for %s (%d days left)", domain.domain_name, ssl_days)

    # --- Domain Alert ---
    domain_days = _days_until(domain.domain_expiry_date)
    if domain_days is not None and domain_days <= DOMAIN_ALERT_DAYS and not domain.alert_sent_domain:
        sent = send_domain_alert(domain.domain_name, domain.domain_expiry_date, domain_days)
        if sent:
            domain.alert_sent_domain = True
            logger.info("Domain alert sent for %s (%d days left)", domain.domain_name, domain_days)

    db.commit()
    db.refresh(domain)
    return summary


def run_all_checks(db: Session) -> list[dict]:
    """Check all domains in the database. Called by scheduler and /check-now."""
    domains = db.query(Domain).all()
    results = []
    for domain in domains:
        try:
            result = check_and_update_domain(db, domain)
            results.append(result)
        except Exception as e:
            logger.error("Failed to check domain %s: %s", domain.domain_name, e)
            results.append({"domain": domain.domain_name, "error": str(e)})
    logger.info("Completed checks for %d domains", len(domains))
    return results
