import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

logger = logging.getLogger(__name__)


def _get_smtp_config(db=None) -> dict:
    """
    Load SMTP config from DB settings if a session is provided,
    otherwise fall back to environment config.
    """
    if db is not None:
        try:
            from app.services.settings_service import get_all
            s = get_all(db)
            return {
                "host":       s.get("smtp_host", ""),
                "port":       int(s.get("smtp_port", 587) or 587),
                "user":       s.get("smtp_user", ""),
                "password":   s.get("smtp_password", ""),
                "from_email": s.get("alert_from_email", ""),
                "to_email":   s.get("alert_to_email", ""),
            }
        except Exception:
            pass

    # Fallback to environment
    from app.config import SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, ALERT_FROM_EMAIL, ALERT_TO_EMAIL
    return {
        "host":       SMTP_HOST,
        "port":       SMTP_PORT,
        "user":       SMTP_USER,
        "password":   SMTP_PASSWORD,
        "from_email": ALERT_FROM_EMAIL,
        "to_email":   ALERT_TO_EMAIL,
    }


def send_email(subject: str, body_html: str, to_email: str = None, db=None) -> bool:
    """
    Send an HTML email via SMTP.
    Pass db session to use DB-stored SMTP settings.
    Returns True on success, False on failure.
    """
    cfg = _get_smtp_config(db)
    recipient = to_email or cfg["to_email"]

    if not cfg["user"] or not cfg["password"]:
        logger.warning("SMTP credentials not configured — skipping email send.")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = cfg["from_email"]
    msg["To"] = recipient
    msg.attach(MIMEText(body_html, "html"))

    try:
        with smtplib.SMTP(cfg["host"], cfg["port"], timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.login(cfg["user"], cfg["password"])
            server.sendmail(cfg["from_email"], recipient, msg.as_string())
        logger.info("Email sent to %s: %s", recipient, subject)
        return True
    except smtplib.SMTPAuthenticationError:
        logger.error("SMTP authentication failed. Check SMTP_USER and SMTP_PASSWORD.")
    except smtplib.SMTPException as e:
        logger.error("SMTP error sending email: %s", e)
    except Exception as e:
        logger.error("Unexpected error sending email: %s", e)

    return False


def send_test_email(db=None) -> tuple[bool, str]:
    """Send a test email to verify SMTP settings. Returns (success, message)."""
    cfg = _get_smtp_config(db)
    if not cfg["user"] or not cfg["password"]:
        return False, "SMTP credentials not configured."

    body = """
    <html><body style="font-family: Arial, sans-serif; color: #333;">
        <h2 style="color: #6366f1;">✅ Test Email</h2>
        <p>Your SMTP settings are working correctly.</p>
        <p>Domain &amp; SSL Expiry Tracker is configured to send alerts to this address.</p>
        <hr/><small style="color: #999;">Domain & SSL Expiry Tracker</small>
    </body></html>
    """
    success = send_email("✅ Test Email — Domain & SSL Tracker", body, db=db)
    if success:
        return True, f"Test email sent successfully to {cfg['to_email']}"
    return False, "Failed to send test email. Check SMTP settings and logs."


def send_ssl_alert(domain_name: str, expiry_date: datetime, days_left: int, db=None) -> bool:
    """Send SSL certificate expiry alert."""
    subject = f"⚠️ SSL Certificate Expiring Soon: {domain_name}"
    body = f"""
    <html><body style="font-family: Arial, sans-serif; color: #333;">
        <h2 style="color: #e67e22;">SSL Certificate Expiry Alert</h2>
        <p>The SSL certificate for <strong>{domain_name}</strong> is expiring soon.</p>
        <table style="border-collapse: collapse; width: 400px;">
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;"><strong>Domain</strong></td>
                <td style="padding: 8px; border: 1px solid #ddd;">{domain_name}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;"><strong>Expiry Date</strong></td>
                <td style="padding: 8px; border: 1px solid #ddd;">{expiry_date.strftime('%Y-%m-%d') if expiry_date else 'Unknown'}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;"><strong>Days Remaining</strong></td>
                <td style="padding: 8px; border: 1px solid #ddd; color: #e67e22;"><strong>{days_left} days</strong></td>
            </tr>
        </table>
        <p style="margin-top: 20px;">Please renew your SSL certificate as soon as possible.</p>
        <hr/><small style="color: #999;">Domain & SSL Expiry Tracker</small>
    </body></html>
    """
    return send_email(subject, body, db=db)


def send_domain_alert(domain_name: str, expiry_date: datetime, days_left: int, db=None) -> bool:
    """Send domain registration expiry alert."""
    subject = f"⚠️ Domain Expiring Soon: {domain_name}"
    body = f"""
    <html><body style="font-family: Arial, sans-serif; color: #333;">
        <h2 style="color: #c0392b;">Domain Expiry Alert</h2>
        <p>The domain registration for <strong>{domain_name}</strong> is expiring soon.</p>
        <table style="border-collapse: collapse; width: 400px;">
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;"><strong>Domain</strong></td>
                <td style="padding: 8px; border: 1px solid #ddd;">{domain_name}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;"><strong>Expiry Date</strong></td>
                <td style="padding: 8px; border: 1px solid #ddd;">{expiry_date.strftime('%Y-%m-%d') if expiry_date else 'Unknown'}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;"><strong>Days Remaining</strong></td>
                <td style="padding: 8px; border: 1px solid #ddd; color: #c0392b;"><strong>{days_left} days</strong></td>
            </tr>
        </table>
        <p style="margin-top: 20px;">Please renew your domain registration to avoid service interruption.</p>
        <hr/><small style="color: #999;">Domain & SSL Expiry Tracker</small>
    </body></html>
    """
    return send_email(subject, body, db=db)
